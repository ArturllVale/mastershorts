from core.json_utils import read_json_async, write_json_async
import os
import re
import json
import time
import glob
import asyncio
import signal
import socket
import shutil
import threading
import subprocess
import uuid
import sys
import httpx
from typing import Optional
from datetime import datetime, timezone

from core.state import jobs, job_queue, concurrency_semaphore, thumbnail_sessions, pending_uploads
from core.config import (
    OUTPUT_DIR, UPLOAD_DIR, BACKEND_DIR,
    MAX_FILE_SIZE_MB, JOB_RETENTION_SECONDS,
    UPLOADS_MAX_GB, OUTPUT_MAX_GB, SOURCE_RETENTION_SECONDS,
    THUMBNAILS_DIR, BILLING_ENABLED, DEBUG_LOGS
)
from core.state import MAX_CONCURRENT_JOBS
from s3_uploader import upload_job_artifacts

if BILLING_ENABLED:
    import cloud
    from cloud import managed_keys, alerts as _alerts
else:
    cloud = None
    managed_keys = None
    _alerts = None

def _relocate_root_job_artifacts(job_id: str, job_output_dir: str) -> bool:
    """
    Backward-compat rescue:
    If main.py accidentally wrote metadata/clips into OUTPUT_DIR root (e.g. output/<jobid>_...),
    move them into output/<job_id>/ so the API can find and serve them.
    """
    try:
        os.makedirs(job_output_dir, exist_ok=True)
        root = OUTPUT_DIR
        pattern = os.path.join(root, f"{job_id}_*_metadata.json")
        meta_candidates = sorted(glob.glob(pattern), key=lambda p: os.path.getmtime(p), reverse=True)
        if not meta_candidates:
            return False

        # Move the newest metadata and its associated clips.
        metadata_path = meta_candidates[0]
        base_name = os.path.basename(metadata_path).replace("_metadata.json", "")

        # Move metadata
        dest_metadata = os.path.join(job_output_dir, os.path.basename(metadata_path))
        if os.path.abspath(metadata_path) != os.path.abspath(dest_metadata):
            shutil.move(metadata_path, dest_metadata)

        # Move any clips that match the same base_name into the job folder
        clip_pattern = os.path.join(root, f"{base_name}_clip_*.mp4")
        for clip_path in glob.glob(clip_pattern):
            dest_clip = os.path.join(job_output_dir, os.path.basename(clip_path))
            if os.path.abspath(clip_path) != os.path.abspath(dest_clip):
                shutil.move(clip_path, dest_clip)

        # Also move any temp_ clips that might remain
        temp_clip_pattern = os.path.join(root, f"temp_{base_name}_clip_*.mp4")
        for clip_path in glob.glob(temp_clip_pattern):
            dest_clip = os.path.join(job_output_dir, os.path.basename(clip_path))
            if os.path.abspath(clip_path) != os.path.abspath(dest_clip):
                shutil.move(clip_path, dest_clip)

        return True
    except Exception:
        return False

def _canonical_clip_file(output_dir, base_name, index):
    """The file to serve for clip ``index``, preferring a derived version."""
    clean = f"{base_name}_clip_{index + 1}.mp4"
    derived = []
    try:
        if os.path.isdir(output_dir):
            for f in os.listdir(output_dir):
                if f.endswith(clean) and (f.startswith("subtitled_") or f.startswith("recut_") or f.startswith("hooked_") or f.startswith("hook_")):
                    derived.append(os.path.join(output_dir, f))
    except Exception:
        pass
    if not derived:
        return clean
    # Highest timestamp wins — that's the most recent styling.
    return os.path.basename(max(derived, key=os.path.getmtime))


def _clips_actually_rendered(job_id, output_dir, base_name, clips):
    """Keep only the clips whose file is really on disk. Returns (kept, missing)."""
    ready_files = (jobs.get(job_id) or {}).get('ready_files') or {}
    kept = []
    for i, clip in enumerate(clips):
        clip_filename = (ready_files.get(i)
                         or _canonical_clip_file(output_dir, base_name, i))
        clip_path = os.path.join(output_dir, clip_filename)
        try:
            present = os.path.getsize(clip_path) > 0
        except OSError:
            present = False
        if not present:
            print(f"⚠️  Clip {i + 1} of {job_id} never rendered "
                  f"({clip_filename}) — dropping it from the result.")
            continue
        clip['video_url'] = f"/videos/{job_id}/{clip_filename}"
        kept.append(clip)
    return kept, len(clips) - len(kept)


def _strip_burned_captions(output_dir, filename):
    while True:
        m = re.match(r'^subtitled_\d+_(.+)$', filename)
        if not m or not os.path.exists(os.path.join(output_dir, m.group(1))):
            return filename
        filename = m.group(1)


def _strip_burned_hook(output_dir, filename):
    while True:
        m = re.match(r'^(?:hooked_\d+_|hook_)(.+)$', filename)
        if not m or not os.path.exists(os.path.join(output_dir, m.group(1))):
            return filename
        filename = m.group(1)


def _reapply_captions(job_id, clip_index, video_path):
    try:
        meta_files = glob.glob(os.path.join(OUTPUT_DIR, job_id, "*_metadata.json"))
        if not meta_files:
            return None
        with open(meta_files[0], 'r') as f:
            data = json.load(f)
        transcript = data.get('transcript')
        clips = data.get('shorts', [])
        if not transcript or clip_index >= len(clips):
            return None
        clip = clips[clip_index]
        import main as _main
        import recut
        recipe_segments = (clip.get('recipe') or {}).get('segments')
        if recipe_segments:
            v_transcript = recut.virtual_transcript(transcript, recipe_segments)
            return _main.auto_caption_clip(
                video_path, v_transcript, 0.0,
                recut.total_duration(recipe_segments))
        return _main.auto_caption_clip(video_path, transcript,
                                       clip['start'], clip['end'])
    except Exception as e:
        print(f"⚠️  Could not re-apply captions to {video_path}: {e}")
        return None


def _recover_jobs_from_disk():
    recovered = 0
    try:
        entries = os.listdir(OUTPUT_DIR)
    except FileNotFoundError:
        return
    for job_id in entries:
        job_path = os.path.join(OUTPUT_DIR, job_id)
        if not os.path.isdir(job_path) or job_id in jobs:
            continue
        json_files = glob.glob(os.path.join(job_path, "*_metadata.json"))
        if not json_files:
            continue
        try:
            with open(json_files[0], 'r') as f:
                data = json.load(f)
            base_name = os.path.basename(json_files[0]).replace('_metadata.json', '')
            clips = data.get('shorts', [])
            for i, clip in enumerate(clips):
                if not clip.get('video_url'):
                    clip['video_url'] = (
                        f"/videos/{job_id}/"
                        f"{_canonical_clip_file(job_path, base_name, i)}")
            owner = None
            owner_path = os.path.join(job_path, ".owner")
            if os.path.exists(owner_path):
                with open(owner_path) as f:
                    raw = f.read().strip()
                owner = int(raw) if raw.isdigit() else (raw or None)
            jobs[job_id] = {
                'status': 'completed',
                'logs': ["♻️ Job recovered from disk after server restart."],
                'output_dir': job_path,
                'user_id': owner,
                'result': {'clips': clips, 'cost_analysis': data.get('cost_analysis')},
            }
            recovered += 1
        except Exception as e:
            print(f"⚠️ Could not recover job {job_id}: {e}")
    if recovered:
        print(f"♻️  Recovered {recovered} completed job(s) from disk.")

_RESUME_FILE = ".resume.json"
MAX_RESUME_ATTEMPTS = 2
INSTANCE_ID = os.environ.get("INSTANCE_ID") or socket.gethostname()
_INSTANCE_MARKER = ".instance"
HEARTBEAT_EVERY = 10
HEARTBEAT_STALE_AFTER = 60
RESUME_SCAN_INTERVAL = 30
HANDOVER_CHECK_INTERVAL = 5
DRAIN_TIMEOUT_SECONDS = int(os.environ.get("DRAIN_TIMEOUT_SECONDS", "840"))
PROXY_DRAIN_SECONDS = float(os.environ.get("PROXY_DRAIN_SECONDS", "20"))
HARD_EXIT_SECONDS = float(os.environ.get("HARD_EXIT_SECONDS", "30"))
_draining = False
_stopping = False
_running_jobs: set = set()


def _manifest_path(job_id):
    return os.path.join(OUTPUT_DIR, job_id, _RESUME_FILE)

def _read_manifest(job_id):
    try:
        with open(_manifest_path(job_id)) as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"⚠️ Bad resume manifest for {job_id}: {e}")
        return None

def _touch_manifest(job_id, now=None):
    m = _read_manifest(job_id)
    if m is None:
        return
    m["heartbeat"] = now if now is not None else time.time()
    m["instance"] = INSTANCE_ID
    try:
        with open(_manifest_path(job_id), "w") as f:
            json.dump(m, f)
    except Exception as e:
        print(f"⚠️ Could not heartbeat manifest for {job_id}: {e}")

def _manifest_busy_elsewhere(m, now=None):
    now = time.time() if now is None else now
    return (m.get("instance") not in (None, INSTANCE_ID)
            and now - float(m.get("heartbeat") or 0) < HEARTBEAT_STALE_AFTER)

def _write_instance_marker():
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(os.path.join(OUTPUT_DIR, _INSTANCE_MARKER), "w") as f:
            f.write(INSTANCE_ID)
    except Exception as e:
        print(f"⚠️ Could not write instance marker: {e}")

def _read_instance_marker():
    try:
        with open(os.path.join(OUTPUT_DIR, _INSTANCE_MARKER)) as f:
            return f.read().strip()
    except Exception:
        return None

def _begin_drain(reason):
    global _draining
    if not _draining:
        _draining = True
        print(f"⏸️ Draining ({reason}): finishing {len(_running_jobs)} running job(s), "
              f"starting none.")

def _check_instance_marker():
    other = _read_instance_marker()
    if other and other != INSTANCE_ID:
        _begin_drain(f"newer instance {other} is up")
        return True
    return False

async def _handover_watch():
    while not _draining:
        await asyncio.sleep(HANDOVER_CHECK_INTERVAL)
        _check_instance_marker()

async def _resume_scan():
    while True:
        await asyncio.sleep(RESUME_SCAN_INTERVAL)
        if _draining:
            continue
        try:
            _resume_interrupted_jobs()
        except Exception as e:
            print(f"⚠️ Resume scan failed: {e}")

async def _drain_then_exit(previous_handler, timeout=None, proxy_grace=None,
                           hard_exit_after=None):
    timeout = DRAIN_TIMEOUT_SECONDS if timeout is None else timeout
    proxy_grace = PROXY_DRAIN_SECONDS if proxy_grace is None else proxy_grace
    hard_exit_after = HARD_EXIT_SECONDS if hard_exit_after is None else hard_exit_after
    deadline = time.time() + timeout
    while _running_jobs and time.time() < deadline:
        await asyncio.sleep(1)
    if _running_jobs:
        print(f"⏱️ Drain timeout after {timeout}s with {len(_running_jobs)} job(s) still "
              f"running — they will resume on the next instance.")
    else:
        print("✅ Drained: no running jobs.")
    if proxy_grace > 0:
        print(f"⏳ Serving {proxy_grace:.0f}s more while the proxy drops this instance.")
        await asyncio.sleep(proxy_grace)
    print("👋 Shutting down.")
    if hard_exit_after > 0:
        threading.Timer(hard_exit_after, _hard_exit).start()
    if callable(previous_handler):
        previous_handler(signal.SIGTERM, None)
    else:
        os._exit(0)

def _hard_exit():
    print(f"⛔ Still alive {HARD_EXIT_SECONDS:.0f}s after the stop signal (a thread "
          f"is hanging) — exiting now.", flush=True)
    os._exit(0)

def _install_drain_signal_handler():
    previous = signal.getsignal(signal.SIGTERM)
    loop = asyncio.get_running_loop()

    def on_sigterm():
        global _stopping
        _stopping = True
        _begin_drain("SIGTERM")
        asyncio.ensure_future(_drain_then_exit(previous))

    try:
        loop.add_signal_handler(signal.SIGTERM, on_sigterm)
    except (NotImplementedError, RuntimeError, ValueError) as e:
        print(f"⚠️ Drain-on-SIGTERM unavailable ({e}); jobs will resume on restart instead.")

def _write_resume_manifest(job_id, cmd, priority, user_id, reservation_id, watermark,
                           webhook_url=None, webhook_secret=None, base_url=None,
                           partial=None, env=None):
    try:
        path = os.path.join(OUTPUT_DIR, job_id, _RESUME_FILE)
        llm_cfg = {}
        if env:
            for k in ("LLM_PROVIDER", "LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY", "LLM_FALLBACK_MODELS", "GEMINI_API_KEY"):
                if env.get(k):
                    llm_cfg[k] = env[k]
        with open(path, "w") as f:
            json.dump({
                "cmd": cmd, "priority": priority,
                "user_id": None if user_id is None else str(user_id),
                "reservation_id": reservation_id,
                "watermark": bool(watermark), "attempts": 0,
                "webhook_url": webhook_url,
                "webhook_secret": webhook_secret,
                "base_url": base_url,
                "partial": partial,
                "llm_cfg": llm_cfg,
            }, f)
    except Exception as e:
        print(f"⚠️ Could not write resume manifest for {job_id}: {e}")

def _clear_resume_manifest(job_id):
    try:
        os.remove(os.path.join(OUTPUT_DIR, job_id, _RESUME_FILE))
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"⚠️ Could not clear resume manifest for {job_id}: {e}")

def _resume_interrupted_jobs() -> set:
    keep_reservations: set = set()
    try:
        entries = os.listdir(OUTPUT_DIR)
    except FileNotFoundError:
        return keep_reservations
    resumed = 0
    for job_id in entries:
        job_path = os.path.join(OUTPUT_DIR, job_id)
        manifest_path = os.path.join(job_path, _RESUME_FILE)
        if not os.path.isfile(manifest_path):
            continue
        if glob.glob(os.path.join(job_path, "*_metadata.json")):
            _clear_resume_manifest(job_id)
            continue
        try:
            with open(manifest_path) as f:
                m = json.load(f)
        except Exception as e:
            print(f"⚠️ Bad resume manifest for {job_id}: {e}")
            continue

        if m.get("reservation_id"):
            keep_reservations.add(str(m["reservation_id"]))
        if job_id in _running_jobs:
            continue
        if _manifest_busy_elsewhere(m):
            continue

        attempts = int(m.get("attempts", 0)) + 1
        user_id = m.get("user_id")
        reservation_id = m.get("reservation_id")
        if attempts > MAX_RESUME_ATTEMPTS:
            print(f"🛑 Job {job_id} exceeded {MAX_RESUME_ATTEMPTS} resume attempts — giving up.")
            _clear_resume_manifest(job_id)
            if reservation_id:
                keep_reservations.discard(str(reservation_id))
            continue

        env = os.environ.copy()
        try:
            from cloud import proxy_ledger as _pl
            if BILLING_ENABLED and _pl.budget_exceeded_sync():
                env.pop("PROXY_URL", None)
        except Exception:
            pass
        if BILLING_ENABLED and user_id is not None:
            try:
                env["GEMINI_API_KEY"] = managed_keys.gemini_key()
            except Exception:
                pass
        if m.get("watermark"):
            env["WATERMARK"] = "1"
        else:
            env.pop("WATERMARK", None)
        partial = m.get("partial")
        if partial and partial.get("processed_minutes"):
            env["MAX_SOURCE_MINUTES"] = str(partial["processed_minutes"])
        else:
            env.pop("MAX_SOURCE_MINUTES", None)
        if m.get("llm_cfg"):
            env.update(m["llm_cfg"])

        m["attempts"] = attempts
        try:
            with open(manifest_path, "w") as f:
                json.dump(m, f)
        except Exception:
            pass

        jobs[job_id] = {
            'status': 'queued',
            'logs': [f"♻️ Resuming your video after a server update (attempt {attempts})."],
            'cmd': m.get("cmd"),
            'env': env,
            'output_dir': job_path,
            'user_id': None if user_id is None else user_id,
            'reservation_id': reservation_id,
            'watermark': bool(m.get("watermark")),
            'partial': partial or None,
            'webhook_url': m.get("webhook_url"),
            'webhook_secret': m.get("webhook_secret"),
            'base_url': m.get("base_url"),
        }
        priority = int(m.get("priority", 2))
        from core.state import _enqueue_job
        _enqueue_job(job_id, priority)
        resumed += 1
    if resumed:
        print(f"♻️  Re-enqueued {resumed} interrupted job(s) after restart.")
    return keep_reservations


def _dir_size(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total

def _enforce_uploads_size_cap():
    cap = UPLOADS_MAX_GB * 1024 ** 3
    if cap <= 0:
        return
    used = _dir_size(UPLOAD_DIR)
    if used <= cap:
        return
    files = []
    for name in os.listdir(UPLOAD_DIR):
        p = os.path.join(UPLOAD_DIR, name)
        if os.path.isfile(p):
            try:
                files.append((os.path.getmtime(p), p, os.path.getsize(p)))
            except OSError:
                pass
    files.sort()
    print(f"🧹 Uploads at {used / 1024**3:.1f} GB (cap {UPLOADS_MAX_GB} GB) — trimming.")
    for _mtime, path, size in files:
        if used <= cap:
            break
        try:
            os.remove(path)
            used -= size
            print(f"🧹 Size cap: removed upload {os.path.basename(path)}")
        except OSError:
            pass

def _enforce_output_size_cap():
    cap = OUTPUT_MAX_GB * 1024 ** 3
    if cap <= 0:
        return
    used = _dir_size(OUTPUT_DIR)
    if used <= cap:
        return
    thumbs = os.path.basename(THUMBNAILS_DIR)
    candidates = []
    for job_id in os.listdir(OUTPUT_DIR):
        if job_id == thumbs:
            continue
        p = os.path.join(OUTPUT_DIR, job_id)
        if os.path.isdir(p):
            try:
                candidates.append((os.path.getmtime(p), p, job_id))
            except OSError:
                pass
    candidates.sort()
    print(f"🧹 Output dir at {used / 1024**3:.1f} GB (cap {OUTPUT_MAX_GB} GB) — trimming.")
    for _mtime, path, job_id in candidates:
        if used <= cap:
            break
        size = _dir_size(path)
        shutil.rmtree(path, ignore_errors=True)
        jobs.pop(job_id, None)
        used -= size
        print(f"🧹 Size cap: purged {job_id} ({size / 1024**2:.0f} MB)")

def _sweep_retained_sources(now=None):
    if SOURCE_RETENTION_SECONDS >= JOB_RETENTION_SECONDS:
        return
    now = time.time() if now is None else now
    for job_id in os.listdir(OUTPUT_DIR):
        if job_id == os.path.basename(THUMBNAILS_DIR):
            continue
        try:
            metas = glob.glob(os.path.join(OUTPUT_DIR, job_id, "*_metadata.json"))
            if not metas:
                continue
            with open(metas[0]) as f:
                name = json.load(f).get('source_video')
            if not name:
                continue
            src = os.path.join(OUTPUT_DIR, job_id, os.path.basename(name))
            if (os.path.exists(src)
                    and now - os.path.getmtime(src) > SOURCE_RETENTION_SECONDS):
                os.remove(src)
                yield job_id
        except Exception:
            continue

async def cleanup_jobs():
    from app import _sweep_pending_uploads
    print("🧹 Cleanup task started.")
    while True:
        try:
            await asyncio.sleep(300)
            now = time.time()
            for job_id in os.listdir(OUTPUT_DIR):
                if job_id == os.path.basename(THUMBNAILS_DIR):
                    continue
                job_path = os.path.join(OUTPUT_DIR, job_id)
                if os.path.isdir(job_path):
                    if now - os.path.getmtime(job_path) > JOB_RETENTION_SECONDS:
                        print(f"🧹 Purging old job: {job_id}")
                        shutil.rmtree(job_path, ignore_errors=True)
                        if job_id in jobs:
                            del jobs[job_id]

            for job_id in _sweep_retained_sources(now):
                print(f"🧹 Dropped retained source for job {job_id}")

            _enforce_output_size_cap()
            _enforce_uploads_size_cap()

            for uid in _sweep_pending_uploads(now):
                print(f"🧹 Expired agent upload slot {uid}")

            for filename in os.listdir(UPLOAD_DIR):
                file_path = os.path.join(UPLOAD_DIR, filename)
                try:
                    if now - os.path.getmtime(file_path) > JOB_RETENTION_SECONDS:
                         os.remove(file_path)
                except Exception: pass
        except Exception as e:
            print(f"⚠️ Cleanup error: {e}")

async def process_queue():
    print(f"🚀 Job Queue Worker started with {MAX_CONCURRENT_JOBS} concurrent slots.")
    while True:
        try:
            _priority, _seq, job_id = await job_queue.get()
            if _draining:
                print(f"⏸️ Draining — leaving {job_id} for the next instance.")
                job_queue.task_done()
                continue

            await concurrency_semaphore.acquire()
            if _draining:
                concurrency_semaphore.release()
                job_queue.task_done()
                print(f"⏸️ Draining — leaving {job_id} for the next instance.")
                continue
            print(f"🔄 Acquired slot for job: {job_id}")
            _running_jobs.add(job_id)
            _touch_manifest(job_id)

            asyncio.create_task(run_job_wrapper(job_id))
        except Exception as e:
            print(f"❌ Queue dispatch error: {e}")
            await asyncio.sleep(1)

_proxy_month = {"month": None, "bytes": 0, "alerted": False}
PROXY_ALERT_GB = 100

def _job_source_url(job) -> Optional[str]:
    cmd = list((job or {}).get("cmd") or [])
    start = next((i + 1 for i, a in enumerate(cmd) if str(a).endswith("main.py")), 0)
    for i in range(start, len(cmd) - 1):
        if cmd[i] in ("-u", "--url"):
            return cmd[i + 1]
    return None

async def _track_proxy_usage(job_id):
    job = jobs.get(job_id) or {}
    if BILLING_ENABLED and job.get("proxy_route"):
        try:
            from cloud import proxy_ledger as _pl
            await _pl.record_download(job_id, job.get("proxy_route"), _job_source_url(job))
        except Exception as e:
            print(f"⚠️ proxy ledger failed for {job_id}: {e}")
    nbytes = job.get("proxy_bytes") or 0
    if not nbytes:
        return
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    if _proxy_month["month"] != month:
        _proxy_month.update(month=month, bytes=0, alerted=False)
    _proxy_month["bytes"] += nbytes
    gb = _proxy_month["bytes"] / 1e9
    if gb >= PROXY_ALERT_GB and not _proxy_month["alerted"] and _alerts:
        _proxy_month["alerted"] = True
        try:
            await _alerts.send_admin_alert(
                "Proxy bandwidth threshold",
                f"Managed downloads have used {gb:.1f} GB of proxy bandwidth in {month} "
                f"(threshold {PROXY_ALERT_GB} GB). Review free-plan usage.",
            )
        except Exception as e:
            print(f"⚠️ Proxy alert failed: {e}")

async def run_job_wrapper(job_id):
    try:
        job = jobs.get(job_id)
        if job:
            await run_job(job_id, job)
    except Exception as e:
         print(f"❌ Job wrapper error {job_id}: {e}")
    finally:
        _clear_resume_manifest(job_id)
        await _settle_reservation(job_id)
        await _archive_managed_job(job_id)
        await _notify_job_webhook(job_id)
        await _record_job_alert(job_id)
        await _track_proxy_usage(job_id)
        await _notify_clips_ready(job_id)
        await _notify_clip_activity(job_id)
        _running_jobs.discard(job_id)
        concurrency_semaphore.release()
        job_queue.task_done()
        print(f"✅ Released slot for job: {job_id}")

async def _archive_managed_job(job_id):
    if not BILLING_ENABLED:
        return
    job = jobs.get(job_id) or {}
    if not job.get("user_id") or job.get("status") != "completed":
        return
    clips = (job.get("result") or {}).get("clips") or []
    if not clips:
        return
    try:
        await cloud.videos.archive_job(job["user_id"], job_id, clips, job["output_dir"])
    except Exception as e:
        print(f"⚠️  R2 archive error for {job_id}: {e}")

def _archive_clip_edit_bg(job_id: str, clip_index: int, filename: str):
    if not BILLING_ENABLED:
        return
    user_id = (jobs.get(job_id) or {}).get("user_id")
    if not user_id:
        return
    output_dir = os.path.join(OUTPUT_DIR, job_id)

    async def _run():
        try:
            await cloud.videos.archive_clip_edit(user_id, job_id, clip_index, output_dir, filename)
        except Exception as e:
            print(f"⚠️  R2 edit archive error for {job_id}: {e}")

    asyncio.create_task(_run())

async def _notify_clips_ready(job_id):
    if not BILLING_ENABLED:
        return
    job = jobs.get(job_id) or {}
    if not job.get("user_id") or job.get("status") != "completed" or job.get("email_sent"):
        return
    clips = (job.get("result") or {}).get("clips") or []
    if not clips:
        return
    job["email_sent"] = True
    try:
        from cloud.database import session as cloud_session
        from cloud.models import User
        from cloud.emails import send_clips_ready_email
        from app import _cloud_config
        async with cloud_session() as s:
            user = await s.get(User, job["user_id"])
        if not user or not user.email:
            return
        title = clips[0].get("video_title_for_youtube_short") or clips[0].get("title") or "Your video"
        await send_clips_ready_email(user.email, title, len(clips),
                                     f"{_cloud_config.settings.frontend_url}/#app")
    except Exception as e:
        print(f"⚠️  Clips-ready email error for {job_id}: {e}")

async def _notify_clip_activity(job_id):
    if not BILLING_ENABLED:
        return
    job = jobs.get(job_id) or {}
    if not job.get("user_id") or job.get("status") != "completed":
        return
    clips = (job.get("result") or {}).get("clips") or []
    if not clips:
        return
    try:
        from cloud.database import session as cloud_session
        from cloud.models import User
        from cloud import metering
        async with cloud_session() as s:
            user = await s.get(User, job["user_id"])
            if not user:
                return
            sub = await metering._active_subscription(s, user.id)
        if sub is None:
            return
        title = clips[0].get("video_title_for_youtube_short") or clips[0].get("title") or "video"
        n = len(clips)
        s_text = "s" if n != 1 else ""
        await _alerts.send_telegram(
            f"🎬 Clips created\n{user.email} ({sub.plan}) — “{title}” ({n} clip{s_text})")
    except Exception as e:
        print(f"⚠️  Clip-activity notify error for {job_id}: {e}")

_ERROR_MARKERS = ("❌", "ERROR:", "Error:", "Traceback", "FATAL", "Exception",
                  "Process failed with exit code", "No metadata file generated",
                  "Execution error:", "Reframe v2 failed")

def _job_error_text(logs) -> str:
    recovered = any("Download succeeded" in ln for ln in logs)
    hits = [ln for ln in logs
            if any(m in ln for m in _ERROR_MARKERS)
            and not (recovered and "Download attempt" in ln)]
    if not hits:
        return " ".join(logs[-10:])
    return " ".join(hits[-6:])

async def _record_job_alert(job_id):
    if not BILLING_ENABLED:
        return
    job = jobs.get(job_id) or {}
    if not job.get("user_id"):
        return
    ok = job.get("status") == "completed"
    err = "" if ok else _job_error_text(job.get("logs", []))
    try:
        await _alerts.record_job_outcome(ok, err)
    except Exception as e:
        print(f"⚠️  Alert recording error for {job_id}: {e}")
    await _track_job_outcome(job, ok, err)

async def _track_job_outcome(job, ok, err):
    try:
        from cloud import analytics as _an
        from sqlalchemy import text as _sa_text
        from cloud import database as _db
        user_id = job.get("user_id")
        job_index = None
        try:
            async with _db.session() as s:
                job_index = (await s.execute(_sa_text(
                    "select count(*) from usage_ledger "
                    "where user_id = :uid and job_type = 'process'"),
                    {"uid": user_id})).scalar()
        except Exception:
            pass
        clips = len(((job.get("result") or {}).get("clips")) or [])
        _an.track(
            "ClipsDelivered" if ok else "JobFailed",
            user_id=user_id,
            job_index=job_index,
            clips=clips if ok else None,
            plan=job.get("user_plan"),
            source="url" if job.get("url") else "upload",
            reason=(_alerts._classify_failure(err) if not ok and err else None),
        )
    except Exception as e:
        print(f"⚠️  Analytics error: {e}")


async def cleanup_jobs():
    from routes.process import _sweep_pending_uploads
    print("🧹 Cleanup task started.")
    while True:
        try:
            await asyncio.sleep(300)
            now = time.time()
            for job_id in os.listdir(OUTPUT_DIR):
                if job_id == os.path.basename(THUMBNAILS_DIR):
                    continue
                job_path = os.path.join(OUTPUT_DIR, job_id)
                if os.path.isdir(job_path):
                    if now - os.path.getmtime(job_path) > JOB_RETENTION_SECONDS:
                        print(f"🧹 Purging old job: {job_id}")
                        shutil.rmtree(job_path, ignore_errors=True)
                        if job_id in jobs:
                            del jobs[job_id]

            for job_id in _sweep_retained_sources(now):
                print(f"🧹 Dropped retained source for job {job_id}")

            _enforce_output_size_cap()
            _enforce_uploads_size_cap()

            for uid in _sweep_pending_uploads(now):
                print(f"🧹 Expired agent upload slot {uid}")

            for filename in os.listdir(UPLOAD_DIR):
                file_path = os.path.join(UPLOAD_DIR, filename)
                try:
                    if now - os.path.getmtime(file_path) > JOB_RETENTION_SECONDS:
                         os.remove(file_path)
                except Exception: pass
        except Exception as e:
            print(f"⚠️ Cleanup error: {e}")


_CREDENTIAL_URL_RE = re.compile(r'(\w+://)[^:/@\s]+:[^@/\s]+@')
WEBHOOK_RETRY_DELAYS = (0, 10, 60)  # seconds before each attempt
WEBHOOK_TIMEOUT = 10.0


def _safe_under(base: str, path: str) -> Optional[str]:
    resolved = os.path.realpath(os.path.join(base, path))
    base_real = os.path.realpath(base)
    return resolved if resolved == base_real or resolved.startswith(base_real + os.sep) else None


def _scrub_secrets(line: str) -> str:
    return _CREDENTIAL_URL_RE.sub(r'\1***:***@', line)


def _visible_logs(logs):
    """Logs to surface to the client.

    Shows a curated, human-friendly whitelist view in pt-BR (log_view.friendly_logs)
    for app users — download percentage, transcription progress, and clip counters —
    with no file paths, model names or pipeline internals.

    DEBUG_LOGS=true forces raw uncurated pipeline logs for developers debugging locally.
    """
    if DEBUG_LOGS:
        return logs
    from log_view import friendly_logs
    return friendly_logs(logs)


def enqueue_output(out, job_id):
    """Reads output from a subprocess and appends it to jobs logs."""
    try:
        for line in iter(out.readline, b''):
            decoded_line = _scrub_secrets(line.decode('utf-8', errors='replace').strip())
            if decoded_line:
                # Internal marker from main.py's downloader, not a log line.
                # Internal marker: a clip finished its whole chain and this is
                # the file to serve for it. Consumed here like PROXY_BYTES so it
                # never reaches the user's log.
                if decoded_line.startswith("CLIP_QUEUED "):
                    try:
                        _, idx_str = decoded_line.split(" ", 1)
                        idx = int(idx_str.strip())
                        if job_id in jobs:
                            jobs[job_id].setdefault('clip_states', {})[idx] = 'queued'
                    except (ValueError, KeyError):
                        pass
                    continue
                if decoded_line.startswith("CLIP_RENDERING "):
                    try:
                        _, idx_str = decoded_line.split(" ", 1)
                        idx = int(idx_str.strip())
                        if job_id in jobs:
                            jobs[job_id].setdefault('clip_states', {})[idx] = 'rendering'
                    except (ValueError, KeyError):
                        pass
                    continue
                if decoded_line.startswith("CLIP_READY "):
                    try:
                        _, index, filename = decoded_line.split(" ", 2)
                        if job_id in jobs:
                            jobs[job_id].setdefault('ready_files', {})[int(index)] = filename
                            jobs[job_id].setdefault('clip_states', {})[int(index)] = 'ready'
                    except ValueError:
                        pass
                    continue
                if decoded_line.startswith("CLIP_FAILED "):
                    try:
                        _, rest = decoded_line.split(" ", 1)
                        idx_str, json_str = rest.split(" ", 1)
                        idx = int(idx_str)
                        import json as _json_inner
                        err = _json_inner.loads(json_str)
                        if job_id in jobs:
                            jobs[job_id].setdefault('clip_states', {})[idx] = 'failed'
                            jobs[job_id].setdefault('clip_errors', {})[idx] = err
                    except Exception:
                        pass
                    continue
                if decoded_line.startswith("JOB_CLIPS_DONE "):
                    # Informational: parent already has per-clip states via CLIP_READY/
                    # CLIP_FAILED. Log it for debugging but don't update state here
                    # (run_job finalizes the job status after the process exits).
                    try:
                        parts = decoded_line.split()
                        n_ready, n_failed = int(parts[1]), int(parts[2])
                        print(f"📊 [Job {job_id}] clips done: {n_ready} ready, {n_failed} failed")
                    except Exception:
                        pass
                    continue

                if decoded_line.startswith("PROXY_BYTES="):
                    try:
                        if job_id in jobs:
                            jobs[job_id]['proxy_bytes'] = int(decoded_line.split("=", 1)[1])
                    except ValueError:
                        pass
                    continue
                if decoded_line.startswith("PROXY_ROUTE="):
                    # Which download attempt won and why the free ones failed;
                    # persisted at job end (cloud/proxy_ledger). Not shown to clients.
                    try:
                        from cloud import proxy_ledger as _pl
                        route = _pl.parse_route_line(decoded_line)
                        if route is not None and job_id in jobs:
                            jobs[job_id]['proxy_route'] = route
                    except Exception:
                        pass
                    continue
                print(f"📝 [Job Output] {decoded_line}")
                if job_id in jobs:
                    jobs[job_id]['logs'].append(decoded_line)
    except Exception as e:
        print(f"Error reading output for job {job_id}: {e}")
    finally:
        out.close()


async def run_job(job_id, job_data):
    """Executes the subprocess for a specific job."""
    
    cmd = job_data['cmd']
    env = job_data['env']
    output_dir = job_data['output_dir']
    
    jobs[job_id]['status'] = 'processing'
    jobs[job_id]['logs'].append("Job started by worker.")
    print(f"🎬 [run_job] Executing command for {job_id}: {' '.join(cmd)}")
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # Merge stderr to stdout
            env=env,
            cwd=BACKEND_DIR
        )
        
        # We need to capture logs in a thread because Popen isn't async
        t_log = threading.Thread(target=enqueue_output, args=(process.stdout, job_id))
        t_log.daemon = True
        t_log.start()
        
        # Async wait for process with incremental updates
        start_wait = time.time()
        last_heartbeat = time.time()
        while process.poll() is None:
            await asyncio.sleep(2)
            if time.time() - last_heartbeat >= HEARTBEAT_EVERY:
                _touch_manifest(job_id)
                last_heartbeat = time.time()
            
            # Check for partial results every 2 seconds
            # Look for metadata file
            try:
                json_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))
                if json_files:
                    target_json = json_files[0]
                    # Read metadata (it might be being written to, so simple try/except or just read)
                    # Use a lock or just robust read? json.load might fail if file is partial.
                    # Usually main.py writes it once at start (based on my review).
                    if os.path.getsize(target_json) > 0:
                        data = await read_json_async(target_json)
                            
                        base_name = os.path.basename(target_json).replace('_metadata.json', '')
                        clips = data.get('shorts', [])
                        cost_analysis = data.get('cost_analysis')
                        
                        # Check which clips actually exist on disk
                        # Only clips main.py has announced as finished. It names
                        # the file itself, so a clip shows up WITH its hook and
                        # captions instead of as the bare reframe, and it is never
                        # served while ffmpeg is still writing it. A clip whose
                        # marker never arrives (it failed) simply stays hidden
                        # until the job ends and the result is rebuilt from disk.
                        ready_files = (jobs.get(job_id) or {}).get('ready_files') or {}
                        ready_clips = []
                        for i, clip in enumerate(clips):
                             clip_filename = ready_files.get(i)
                             if not clip_filename:
                                 continue
                             clip_path = os.path.join(output_dir, clip_filename)
                             if os.path.exists(clip_path) and os.path.getsize(clip_path) > 0:
                                 clip['video_url'] = f"/videos/{job_id}/{clip_filename}"
                                 ready_clips.append(clip)
                        
                        if ready_clips:
                             jobs[job_id]['result'] = {'clips': ready_clips, 'cost_analysis': cost_analysis}
            except Exception as e:
                # Ignore read errors during processing
                pass

        returncode = process.returncode
        
        if returncode == 0:
            jobs[job_id]['logs'].append("Process finished successfully.")

            # Self-host: silent AWS S3 backup. Cloud mode stores to R2 instead
            # (see _archive_managed_job), so skip the redundant/paid AWS upload.
            if not BILLING_ENABLED:
                loop = asyncio.get_event_loop()
                loop.run_in_executor(None, upload_job_artifacts, output_dir, job_id)

            # Find result JSON
            json_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))
            if not json_files:
                # Backward-compat rescue if outputs were written to OUTPUT_DIR root
                if _relocate_root_job_artifacts(job_id, output_dir):
                    json_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))
            if json_files:
                target_json = json_files[0]
                data = await read_json_async(target_json)

                # Enhance result with video URLs
                base_name = os.path.basename(target_json).replace('_metadata.json', '')
                clips = data.get('shorts', [])
                cost_analysis = data.get('cost_analysis')

                rendered, missing = _clips_actually_rendered(
                    job_id, output_dir, base_name, clips)

                # ── Canonical job-status policy ──────────────────────────────
                # Drive the final status from the per-clip states recorded by
                # enqueue_output (CLIP_READY / CLIP_FAILED markers). Fall back
                # to the filesystem check when no clip-state markers arrived
                # (e.g. main.py from an older deploy or a skip-analysis run).
                from services.clip_state import compute_job_status as _compute_job_status
                clip_states_map = (jobs.get(job_id) or {}).get('clip_states') or {}
                if clip_states_map:
                    clip_statuses = list(clip_states_map.values())
                    final_status = _compute_job_status(clip_statuses)
                else:
                    # Legacy fallback: no markers → derive from filesystem
                    final_status = 'completed' if rendered else 'failed'

                jobs[job_id]['status'] = final_status

                if final_status == 'failed' and not rendered:
                    jobs[job_id]['logs'].append(
                        "No clips could be rendered from this video.")
                else:
                    if missing:
                        jobs[job_id]['logs'].append(
                            f"⚠️ {missing} of {len(clips)} clips failed to render.")
                    if final_status == 'partial':
                        n_failed = sum(1 for s in clip_states_map.values() if s == 'failed')
                        jobs[job_id]['logs'].append(
                            f"⚠️ Job finished partially: {len(rendered)} clips ready, "
                            f"{n_failed} failed.")
                    jobs[job_id]['result'] = {'clips': rendered, 'cost_analysis': cost_analysis}
            else:
                jobs[job_id]['status'] = 'failed'
                jobs[job_id]['logs'].append("No metadata file generated.")
        else:
            jobs[job_id]['status'] = 'failed'
            jobs[job_id]['logs'].append(_scrub_secrets(f"Process failed with exit code {returncode}"))
            
    except Exception as e:
        jobs[job_id]['status'] = 'failed'
        # Exception text can embed URLs with credentials (e.g. the proxy URL
        # inside a yt-dlp/httpx error) — scrub before it reaches client logs.
        jobs[job_id]['logs'].append(_scrub_secrets(f"Execution error: {str(e)}"))


def _sign_webhook(body: bytes, secret: str) -> str:
    import hmac as _hmac
    import hashlib as _hashlib
    return "sha256=" + _hmac.new(secret.encode(), body, _hashlib.sha256).hexdigest()


async def _webhook_clip_entries(job_id, job):
    """The payload's clip list: absolute URLs, plus durable R2 links when the
    job was archived (a webhook consumer usually fetches later, after the
    1-hour local retention would have expired the /videos path)."""
    base = (job.get('base_url') or os.environ.get("PUBLIC_API_URL", "")).rstrip("/")
    clips = (job.get('result') or {}).get('clips') or []
    entries = []
    for i, clip in enumerate(clips):
        rel = clip.get('video_url') or ""
        entries.append({
            "index": i,
            "title": clip.get('title') or clip.get('video_title_for_youtube_short'),
            "video_url": f"{base}{rel}" if rel.startswith("/") and base else rel,
        })
    if BILLING_ENABLED and job.get('user_id'):
        try:
            from sqlalchemy import select as _select
            from cloud.database import session as cloud_session
            from cloud.models import UserVideo
            from cloud import storage as _storage
            async with cloud_session() as s:
                vids = list((await s.execute(
                    _select(UserVideo).where(UserVideo.job_id == job_id)
                )).scalars())
            for v in vids:
                if v.clip_index is not None and v.clip_index < len(entries):
                    entries[v.clip_index]["download_url"] = _storage.presigned_get(
                        v.r2_key, expires=24 * 3600)
        except Exception as e:
            print(f"⚠️ Webhook R2 links failed for {job_id}: {e}")
    return entries


async def _deliver_webhook(url, body: bytes, secret):
    headers = {"Content-Type": "application/json", "User-Agent": "OpenShorts-Webhook/1.0"}
    if secret:
        headers["X-OpenShorts-Signature"] = _sign_webhook(body, secret)
    from security_utils import assert_public_url, UnsafeURLError
    loop = asyncio.get_event_loop()
    for attempt, delay in enumerate(WEBHOOK_RETRY_DELAYS, 1):
        if delay:
            await asyncio.sleep(delay)
        try:
            # Re-resolve on every attempt: the submit-time check is stale by now.
            await loop.run_in_executor(None, assert_public_url, url)
            async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT,
                                         follow_redirects=False) as client:
                resp = await client.post(url, content=body, headers=headers)
            if resp.status_code < 300:
                print(f"🪝 Webhook delivered to {url} (attempt {attempt})")
                return
            print(f"⚠️ Webhook attempt {attempt} to {url}: HTTP {resp.status_code}")
        except UnsafeURLError as e:
            print(f"🛑 Webhook URL no longer safe, dropping: {e}")
            return
        except Exception as e:
            print(f"⚠️ Webhook attempt {attempt} to {url} failed: {e}")
    print(f"❌ Webhook to {url} gave up after {len(WEBHOOK_RETRY_DELAYS)} attempts.")


async def _notify_job_webhook(job_id):
    """Fire the caller's webhook for a terminal job. Runs inside run_job_wrapper's
    finally AFTER the R2 archive, so durable links exist; the actual delivery
    (with its retry sleeps) is detached so the worker slot frees immediately."""
    job = jobs.get(job_id) or {}
    url = job.get('webhook_url')
    if not url or job.get('webhook_sent'):
        return
    job['webhook_sent'] = True
    status = job.get('status')
    # completed and partial both have at least one ready clip to deliver.
    has_clips = status in ('completed', 'partial')
    payload = {
        "event": "job.completed" if has_clips else "job.failed",
        "job_id": job_id,
        "job_status": status,    # canonical field — consumers should use this
        "status": status,        # backward-compat alias
        "clips": (await _webhook_clip_entries(job_id, job)) if has_clips else [],
    }
    # Include per-clip state details so consumers can act on individual failures.
    clip_states_map = job.get('clip_states') or {}
    if clip_states_map:
        # Normalise to a list ordered by clip index.
        max_idx = max(int(k) for k in clip_states_map)
        payload["clip_states"] = [
            clip_states_map.get(i, "unknown") for i in range(max_idx + 1)
        ]
        clip_errors_map = job.get('clip_errors') or {}
        if clip_errors_map:
            payload["clip_errors"] = {
                str(k): v for k, v in clip_errors_map.items()
            }
    if not has_clips:
        payload["error"] = _job_error_text(job.get('logs', []))[-500:]
    body = json.dumps(payload).encode()
    asyncio.create_task(_deliver_webhook(url, body, job.get('webhook_secret')))



async def _settle_reservation(job_id):
    if not BILLING_ENABLED:
        return
    job = jobs.get(job_id) or {}
    reservation_id = job.get('reservation_id')
    if not reservation_id:
        return
    try:
        if job.get('status') in ('completed', 'partial'):
            await cloud.metering.commit_reservation(reservation_id)
        else:
            await cloud.metering.release_reservation(reservation_id)
    except Exception as e:
        print(f"⚠️  Reservation settle error for {job_id}: {e}")


def _owned_by(record, uid: str) -> bool:
    owner = record.get('user_id') if isinstance(record, dict) else None
    return owner is not None and str(owner) == uid


def _rm_under(base_dir: str, relative: str):
    """Remove a file or directory, refusing anything that escapes ``base_dir``."""
    target = _safe_under(base_dir, relative)
    if not target or target == os.path.realpath(base_dir):
        return
    if os.path.isdir(target):
        shutil.rmtree(target, ignore_errors=True)
    else:
        try:
            os.remove(target)
        except OSError:
            pass


def _purge_local_jobs_for_user(user_id) -> int:
    """Delete this user's working files and in-memory records from local disk.

    Called by cloud/account.py when an account is erased. The durable copies
    live on R2 and are deleted there; these are the working files on the API's
    own disk, which would otherwise sit around until the one-hour cleanup sweep
    — and thumbnails not even then, because that sweep skips their directory.

    Three stores, because each records ownership differently:
      - clip jobs: the ``.owner`` file every managed job writes, so jobs
        recovered from disk after a restart (no in-memory record) count too;
      - SaaSShorts jobs (``output/saas_<id>``): ``saas_jobs`` only, no marker
        file, so a restart loses the link and those age out on the sweep;
      - thumbnail sessions (``output/thumbnails/<id>`` plus the source video in
        ``uploads/``): likewise in-memory only.

    Blocking: rmtree over gigabytes of video. Callers must run it in a thread.
    """
    uid = str(user_id)
    removed = 0

    job_ids = {jid for jid, job in list(jobs.items()) if _owned_by(job, uid)}
    thumbs_dir_name = os.path.basename(THUMBNAILS_DIR)
    try:
        entries = os.listdir(OUTPUT_DIR)
    except OSError:
        entries = []
    for job_id in entries:
        # Never a job, and it backs a StaticFiles mount: deleting the directory
        # itself 500s every /thumbnails request until the process restarts.
        if job_id == thumbs_dir_name:
            continue
        try:
            with open(os.path.join(OUTPUT_DIR, job_id, ".owner")) as f:
                if f.read().strip() == uid:
                    job_ids.add(job_id)
        except OSError:
            continue

    for job_id in job_ids:
        _rm_under(OUTPUT_DIR, job_id)
        jobs.pop(job_id, None)
        # Source uploads are named "<job_id>_<filename>" (see /api/process).
        for path in glob.glob(os.path.join(UPLOAD_DIR, f"{glob.escape(job_id)}_*")):
            try:
                os.remove(path)
            except OSError:
                pass
        removed += 1

    for sid, sess in list(thumbnail_sessions.items()):
        if not _owned_by(sess, uid):
            continue
        # Generated thumbnails are served publicly at /thumbnails/<id>/... and
        # nothing else ever deletes them.
        _rm_under(THUMBNAILS_DIR, sid)
        video_path = sess.get('video_path')
        if video_path:
            _rm_under(UPLOAD_DIR, os.path.basename(video_path))
        thumbnail_sessions.pop(sid, None)
        removed += 1

    if removed:
        print(f"🗑️  Purged {removed} local work item(s) for erased user {uid}.")
    return removed
