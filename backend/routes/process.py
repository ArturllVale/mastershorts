import aiofiles
import os
import sys
import uuid
import json
import asyncio
import subprocess
import zipfile
import hmac
import hashlib
import time
import shutil
import glob
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict

from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, Body, Header, Form, File, UploadFile
from fastapi.responses import JSONResponse, FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel

import llm_backend
import s3_uploader
from core.json_utils import read_json_async, write_json_async
from core.models import *
from core.config import (
    UPLOAD_DIR, OUTPUT_DIR, MAX_FILE_SIZE_MB, QUALITY_GATE_MIN_HEIGHT, MIN_SOURCE_SECONDS,
    QUALITY_PROBE_SCRIPT, DISABLE_YOUTUBE_URL, BILLING_ENABLED, JOB_RETENTION_SECONDS,
    OUTPUT_MAX_GB, UPLOADS_MAX_GB, UPLOAD_TTL_SECONDS, SOURCE_URL_TTL_SECONDS,
    HEARTBEAT_STALE_AFTER, LAYOUT_ENV, LAYOUT_IMPLIES
)
from core.state import (
    jobs, pending_uploads, thumbnail_sessions, concurrency_semaphore, job_queue, _restore_locks, _enqueue_job
)
from services.job_queue import (
    _write_resume_manifest,
    _read_manifest,
    _manifest_busy_elsewhere,
    _visible_logs,
    _canonical_clip_file,
    _recover_jobs_from_disk,
    _draining,
    retry_job,
)

# We need some helper functions from app.py
from app import (
    require_managed_entitlement,
    _cloud_config,
    resolve_gemini,
    gemini_missing_error,
    _assert_job_owner,
    reserve_managed_action,
    reserve_process_minutes,
    _owner_id,
    _metering,
)


if BILLING_ENABLED:
    import cloud
else:
    cloud = None

router = APIRouter()


async def _probe_youtube_quality(url: str) -> dict:
    """Run quality_probe.py in a worker thread; {} on any failure (fail-open)."""
    def _run():
        try:
            proc = subprocess.run(
                [sys.executable, QUALITY_PROBE_SCRIPT, "--url", url],
                capture_output=True, timeout=75,
            )
            return json.loads(proc.stdout.decode(errors="replace").strip() or "{}")
        except Exception as e:
            print(f"⚠️ Quality probe failed ({e}); starting job without gate.")
            return {}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)


def _media_duration_seconds(path: str) -> float:
    """Container duration via ffprobe; 0.0 on any failure (fail-open)."""
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, timeout=30)
        return float(proc.stdout.decode().strip() or 0)
    except Exception:
        return 0.0


def _reject_short_source(duration: float):
    raise HTTPException(status_code=400, detail=(
        f"This video is only {int(duration)}s long — clip generation needs at "
        f"least {MIN_SOURCE_SECONDS}s of material to cut from. It already is "
        f"short-form content."))


def _upload_url_base(request):
    return os.environ.get("PUBLIC_API_URL", "").rstrip("/") or str(request.base_url).rstrip("/")


@router.post("/api/uploads")
async def create_upload(request: Request):
    """Reserve an upload slot. Body (JSON, optional): {"filename": "..."}."""
    user_id = await _owner_id(request)
    if BILLING_ENABLED and user_id is None:
        raise HTTPException(status_code=401, detail="Sign in or use an API key to upload")
    try:
        body = await request.json()
    except Exception:
        body = {}
    filename = os.path.basename(str((body or {}).get("filename") or "video.mp4")) or "video.mp4"
    upload_id = str(uuid.uuid4())
    pending_uploads[upload_id] = {
        "user_id": user_id,
        "filename": filename,
        "path": os.path.join(UPLOAD_DIR, f"pending_{upload_id}_{filename}"),
        "created": time.time(),
        "bytes": 0,
        "complete": False,
    }
    return {
        "upload_id": upload_id,
        "upload_url": f"{_upload_url_base(request)}/api/uploads/{upload_id}",
        "method": "PUT",
        "max_mb": MAX_FILE_SIZE_MB,
        "expires_in": UPLOAD_TTL_SECONDS,
        "hint": "PUT the raw video bytes to upload_url (e.g. curl -T video.mp4 <upload_url>), "
                "then call /api/process (or the process_video tool) with this upload_id. "
                "The slot and file are deleted after expires_in seconds if unused, or "
                "DELETE this URL to drop them sooner.",
    }


@router.put("/api/uploads/{upload_id}")
async def put_upload(upload_id: str, request: Request):
    """Receive the raw video body for a reserved slot. Streams to disk, capped
    at MAX_FILE_SIZE_MB; a second PUT replaces the first."""
    slot = pending_uploads.get(upload_id)
    if not slot or time.time() - slot["created"] > UPLOAD_TTL_SECONDS:
        pending_uploads.pop(upload_id, None)
        raise HTTPException(status_code=404, detail="Unknown or expired upload_id")
    limit_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    size = 0
    async with aiofiles.open(slot["path"], 'wb') as out:
        async for chunk in request.stream():
            size += len(chunk)
            if size > limit_bytes:
                await out.close()
                os.remove(slot["path"])
                raise HTTPException(status_code=413, detail=f"File too large. Max size {MAX_FILE_SIZE_MB}MB")
            await out.write(chunk)
    if size == 0:
        os.remove(slot["path"])
        raise HTTPException(status_code=400, detail="Empty body")
    slot.update({"bytes": size, "complete": True})
    duration = await asyncio.get_event_loop().run_in_executor(None, _media_duration_seconds, slot["path"])
    if duration <= 0:
        os.remove(slot["path"])
        slot["complete"] = False
        raise HTTPException(status_code=400, detail="The body is not a readable video file")
    return {"upload_id": upload_id, "bytes": size, "duration_seconds": round(duration, 1),
            "hint": "Now call /api/process with upload_id."}


@router.delete("/api/uploads/{upload_id}")
async def delete_upload(upload_id: str, request: Request):
    """Drop a slot and its file before it expires (owner only in cloud mode)."""
    slot = pending_uploads.get(upload_id)
    if not slot or (BILLING_ENABLED and slot.get("user_id") != await _owner_id(request)):
        raise HTTPException(status_code=404, detail="Unknown or expired upload_id")
    pending_uploads.pop(upload_id, None)
    try:
        os.remove(slot["path"])
    except OSError:
        pass
    return {"deleted": upload_id}


def _sweep_pending_uploads(now=None):
    """Expire agent upload slots older than UPLOAD_TTL_SECONDS (file included).
    Returns the ids removed. Called from the cleanup loop; pure enough to test."""
    now = now or time.time()
    gone = []
    for uid, slot in list(pending_uploads.items()):
        if now - slot["created"] > UPLOAD_TTL_SECONDS:
            pending_uploads.pop(uid, None)
            try:
                os.remove(slot["path"])
            except OSError:
                pass
            gone.append(uid)
    return gone


def _take_pending_upload(upload_id, user_id):
    """The completed upload for this caller, or an HTTPException."""
    slot = pending_uploads.get(upload_id)
    if not slot or (BILLING_ENABLED and slot.get("user_id") != user_id):
        raise HTTPException(status_code=404, detail="Unknown or expired upload_id")
    if not slot.get("complete") or not os.path.exists(slot["path"]):
        raise HTTPException(status_code=409, detail="Upload not received yet: PUT the video to upload_url first")
    return slot


def layout_env(requested):
    """Env overrides for the layouts this job allows. Unknown names are ignored
    rather than rejected: a newer dashboard must not break an older API.

    The special value "auto" hands the choice to Gemini (one call per video).
    It composes with explicit picks: layout_picker only ever adds, so asking for
    "auto,punch_in" means "decide the layout yourself, and punch in regardless".
    "none" is the opposite: it switches the picker OFF for this job even when
    the deployment runs with AUTO_LAYOUT=1, for the user who wants the plain
    single crop and nothing clever.
    """
    env = {}
    for name in requested or []:
        key = str(name).strip().lower()
        if key == "auto":
            env["AUTO_LAYOUT"] = "1"
            continue
        if key == "none":
            env["AUTO_LAYOUT"] = "0"
            continue
        var = LAYOUT_ENV.get(key)
        if not var:
            continue
        env[var] = "1"
        for extra in LAYOUT_IMPLIES.get(key, []):
            env[extra] = "1"
    return env


@router.post("/api/process")
async def process_endpoint(
    request: Request,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    acknowledged: Optional[str] = Form(None),
    output_format: Optional[str] = Form(None),
    layouts: Optional[str] = Form(None),
    force_low_quality: Optional[str] = Form(None),
    webhook_url: Optional[str] = Form(None),
    webhook_secret: Optional[str] = Form(None),
    target_clips: Optional[str] = Form(None),
    clip_min_seconds: Optional[str] = Form(None),
    clip_max_seconds: Optional[str] = Form(None),
    auto_hook: Optional[str] = Form(None),
    auto_hook_style: Optional[str] = Form(None),
    thumbnail_session_id: Optional[str] = Form(None),
    captions: Optional[str] = Form(None),
    upload_id: Optional[str] = Form(None),
    max_minutes: Optional[str] = Form(None),
):
    req_llm_base = request.headers.get("X-LLM-Base-URL") or request.headers.get("x-llm-base-url")
    req_llm_model = request.headers.get("X-LLM-Model") or request.headers.get("x-llm-model")
    req_llm_key = request.headers.get("X-LLM-API-Key") or request.headers.get("x-llm-api-key")
    req_llm_fallback = request.headers.get("X-LLM-Fallback-Models") or request.headers.get("x-llm-fallback-models")

    ack_flag = str(acknowledged).lower() in ("1", "true", "yes")
    # May be lowered by the paid-proxy budget check in the metering block
    # below; self-host never runs that block, so it must default here.
    paid_allowed = True
    force_low = str(force_low_quality).lower() in ("1", "true", "yes")

    # Handle JSON body manually for URL payload
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        url = body.get("url")
        ack_flag = bool(body.get("acknowledged"))
        force_low = bool(body.get("force_low_quality"))
        output_format = body.get("output_format")
        layouts = body.get("layouts")
        webhook_url = body.get("webhook_url")
        webhook_secret = body.get("webhook_secret")
        target_clips = body.get("target_clips")
        clip_min_seconds = body.get("clip_min_seconds")
        clip_max_seconds = body.get("clip_max_seconds")
        auto_hook = body.get("auto_hook")
        auto_hook_style = body.get("auto_hook_style")
        thumbnail_session_id = body.get("thumbnail_session_id")
        captions = body.get("captions")
        upload_id = body.get("upload_id")
        max_minutes = body.get("max_minutes")
        if not req_llm_base and body.get("llm_base_url"):
            req_llm_base = body.get("llm_base_url")
            req_llm_model = req_llm_model or body.get("llm_model")
            req_llm_key = req_llm_key or body.get("llm_api_key")
            req_llm_fallback = req_llm_fallback or body.get("llm_fallback_models")
        elif not req_llm_fallback and body.get("llm_fallback_models"):
            req_llm_fallback = body.get("llm_fallback_models")

    api_key = await resolve_gemini(request)
    has_local_llm = bool(req_llm_base) or (llm_backend.active() and not BILLING_ENABLED)
    if not api_key and not has_local_llm:
        # Self-host with an OpenAI-compatible server configured needs no
        # Google key for the core pipeline: the moment picker runs there and
        # the frame-based stages degrade on their own (layout_picker returns
        # "none", silent videos fail with a message that says why).
        raise gemini_missing_error()

    # Normalize output format (auto = keep pipeline default).
    if output_format not in ("vertical", "horizontal", "square"):
        output_format = "auto"

    # Accepts a JSON list or a comma-separated form field.
    if isinstance(layouts, str):
        layouts = [p for p in layouts.split(",") if p.strip()]
    elif not isinstance(layouts, list):
        layouts = []

    # Module handover (issue #68): reuse the Thumbnail Studio source video and
    # its transcript so publishing to YouTube can flow straight into clip
    # generation without re-uploading or re-transcribing.
    thumb_session = None
    if thumbnail_session_id and not url and not file:
        thumb_session = thumbnail_sessions.get(thumbnail_session_id)
        if not thumb_session:
            raise HTTPException(status_code=404, detail="Thumbnail session not found or expired")
        await _assert_job_owner(request, thumb_session)
        src = thumb_session.get("video_path")
        if not src or not os.path.exists(src):
            raise HTTPException(status_code=404, detail="Source video for this session is no longer on disk")

    # Agent upload (POST /api/uploads + PUT): the file is already on disk.
    upload_slot = None
    if upload_id and not url and not file and not thumb_session:
        upload_slot = _take_pending_upload(upload_id, await _owner_id(request))

    if not url and not file and not thumb_session and not upload_slot:
        raise HTTPException(status_code=400, detail="Must provide URL, File or upload_id")

    # Completion callback: reject unsafe targets NOW (clear 400) — delivery
    # re-validates anyway, but failing at submit is the debuggable behavior.
    if webhook_url:
        from security_utils import assert_public_url, UnsafeURLError
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, assert_public_url, webhook_url)
        except UnsafeURLError as e:
            raise HTTPException(status_code=400, detail=f"Invalid webhook_url: {e}")

    if not ack_flag:
        raise HTTPException(status_code=400, detail="You must confirm you own the content or have rights to process it.")

    if url and DISABLE_YOUTUBE_URL:
        raise HTTPException(status_code=403, detail="YouTube URL ingest is disabled on this deployment. Please upload a file you own.")

    # Pre-flight quality gate: probe the offered resolution BEFORE starting, so
    # the user can abort (refresh cookies / update yt-dlp) instead of burning
    # 20 min on a 360p-only source. Fail-open: any probe error starts normally.
    # The probe also runs under force_low_quality so the short-source check
    # can't be bypassed through the quality-gate confirm.
    if url and (QUALITY_GATE_MIN_HEIGHT > 0 or MIN_SOURCE_SECONDS > 0):
        probe = await _probe_youtube_quality(url)
        # Hard reject, no confirm-and-retry: a too-short source fails the same
        # way on every retry, so letting the user force it just burns the job.
        source_duration = int(probe.get("duration") or 0)
        if MIN_SOURCE_SECONDS > 0 and 0 < source_duration < MIN_SOURCE_SECONDS:
            _reject_short_source(source_duration)
        max_height = int(probe.get("max_height") or 0)
        if not force_low and QUALITY_GATE_MIN_HEIGHT > 0 \
                and 0 < max_height < QUALITY_GATE_MIN_HEIGHT:
            print(f"⚠️ Quality gate: only {max_height}p available for {url} — asking user first.")
            return JSONResponse({
                "needs_confirmation": True,
                "quality_check": {
                    "max_height": max_height,
                    "min_height": QUALITY_GATE_MIN_HEIGHT,
                    "cookies_invalid": bool(probe.get("cookies_invalid")),
                },
            })

    # Capture attestation context for legal record (IP + timestamp + UA)
    client_ip = request.client.host if request.client else "unknown"
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        client_ip = fwd.split(",")[0].strip()
    user_agent = request.headers.get("user-agent", "")
    attestation = {
        "acknowledged": True,
        "ip": client_ip,
        "user_agent": user_agent,
        "timestamp": time.time(),
        "source": ("thumbnail_session" if thumb_session else "upload_id" if upload_slot
                   else "url" if url else "file"),
    }

    job_id = str(uuid.uuid4())
    job_output_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(job_output_dir, exist_ok=True)

    # Prepare Command
    # sys.executable, not "python": bare "python" resolves against PATH, which
    # might be whatever interpreter happens to be first — not the venv
    # running this server. Every job then dies on `import cv2`. The quality
    # probe above already gets this right.
    cmd = [sys.executable, "-u", "main.py"] # -u for unbuffered
    env = os.environ.copy()
    if not paid_allowed:
        # Daily paid-proxy budget hit: this job runs on the free routes only.
        env.pop("PROXY_URL", None)
    if api_key and not req_llm_base:
        env["GEMINI_API_KEY"] = api_key # Override with key from request
    else:
        env.pop("GEMINI_API_KEY", None)  # local-LLM job: main.py must not find a stale key

    if req_llm_base:
        env["LLM_PROVIDER"] = "openai"
        env["LLM_BASE_URL"] = req_llm_base.strip().rstrip("/")
        if req_llm_model:
            env["LLM_MODEL"] = req_llm_model.strip()
        if req_llm_key:
            env["LLM_API_KEY"] = req_llm_key.strip()
        if req_llm_fallback:
            env["LLM_FALLBACK_MODELS"] = req_llm_fallback.strip()
        print(f"[llm] job={job_id} provider=openai url={env['LLM_BASE_URL']} model={env.get('LLM_MODEL', 'default')} fallbacks={env.get('LLM_FALLBACK_MODELS', 'none')}")
    elif req_llm_fallback:
        env["LLM_FALLBACK_MODELS"] = req_llm_fallback.strip()
    # The stdio fix above only covers this process. main.py prints an emoji on
    # its first line and configures nothing, so on a cp1252 console the child
    # still dies before it renders anything -- the server starts and every job
    # fails instead. setdefault, so an explicit PYTHONIOENCODING still wins.
    env.setdefault("PYTHONIOENCODING", "utf-8")

    # Optional layouts are per job. The renderer reads these at import time in
    # the subprocess, so they must be set before Popen — same path WATERMARK
    # already takes.
    chosen = layout_env(layouts)
    env.update(chosen)
    if chosen:
        print(f"[layouts] job={job_id} enabled={sorted(chosen)}")

    # Auto-hook: burn each clip's Gemini hook text during the render. Off when
    # the field is absent, so API/MCP/webhook callers keep their old output
    # byte-for-byte; the dashboard sends an explicit value either way.
    if str(auto_hook).lower() in ("1", "true", "yes"):
        env["AUTO_HOOK"] = "1"
        from hooks import HOOK_STYLES
        if auto_hook_style in HOOK_STYLES:
            env["AUTO_HOOK_STYLE"] = auto_hook_style
        print(f"[auto-hook] job={job_id} style={env.get('AUTO_HOOK_STYLE', 'classic')}")

    # Manual generation controls (discussion #65): optional clip-count target
    # and duration band, forwarded to the selection prompts via the same env
    # overrides the A/B harness already reads (clip_selection.py). All three
    # are honest TARGETS, not guarantees — the model may return fewer clips
    # when the material doesn't hold them. Bad values 400 instead of silently
    # producing something the user didn't ask for.
    def _gen_control(raw, name, lo, hi, integer=False):
        if raw in (None, ""):
            return None
        try:
            val = float(raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"{name} must be a number")
        if integer and val != int(val):
            raise HTTPException(status_code=400, detail=f"{name} must be an integer")
        if not (lo <= val <= hi):
            raise HTTPException(status_code=400,
                                detail=f"{name} must be between {lo:g} and {hi:g}")
        return int(val) if integer else val

    n_clips = _gen_control(target_clips, "target_clips", 1, 15, integer=True)
    min_secs = _gen_control(clip_min_seconds, "clip_min_seconds", 5, 175)
    max_secs = _gen_control(clip_max_seconds, "clip_max_seconds", 10, 180)
    if min_secs is not None and max_secs is not None and max_secs < min_secs + 5:
        raise HTTPException(status_code=400,
                            detail="clip_max_seconds must be at least 5s above clip_min_seconds")
    if n_clips is not None:
        env["CLIP_TARGET_MIN"] = env["CLIP_TARGET_MAX"] = str(n_clips)
    if min_secs is not None:
        env["CLIP_MIN_SECONDS"] = str(min_secs)
    if max_secs is not None:
        env["CLIP_MAX_SECONDS"] = str(max_secs)
    if n_clips is not None or min_secs is not None or max_secs is not None:
        print(f"[gen-controls] job={job_id} clips={n_clips} band={min_secs}-{max_secs}")

    # captions=false: the source already carries burned-in subtitles (or the
    # caller adds its own later), so skip the free auto-caption pass instead
    # of stacking a second layer. Absent → the deployment default (on).
    if captions is not None and str(captions).lower() in ("0", "false", "no"):
        env["AUTO_CAPTIONS"] = "0"
        print(f"[captions] job={job_id} auto-captions off")

    input_path = None
    if url:
        # Keep the downloaded source inside the job dir: the clip editor's
        # re-render path cuts new segments from it, and it ages out with the
        # rest of the job (retention window + OUTPUT_MAX_GB cap) either way.
        cmd.extend(["-u", url, "--keep-original"])
    elif thumb_session:
        # Hardlink (or copy) the session's video under the job's name so source
        # lookup, the clip editor and the preview treat it exactly like a normal
        # upload; the transcript rides along so the pipeline skips Whisper.
        src = thumb_session["video_path"]
        src_duration = _media_duration_seconds(src)
        if MIN_SOURCE_SECONDS > 0 and 0 < src_duration < MIN_SOURCE_SECONDS:
            shutil.rmtree(job_output_dir, ignore_errors=True)
            _reject_short_source(src_duration)
        input_path = os.path.join(UPLOAD_DIR, f"{job_id}_{os.path.basename(src)}")
        try:
            os.link(src, input_path)
        except OSError:
            shutil.copyfile(src, input_path)
        cmd.extend(["-i", input_path])
        # An empty transcript (e.g. a silent or music-only source) is not worth
        # forwarding: main.py would reject it and retranscribe anyway.
        if thumb_session.get("transcript_ready") and (thumb_session.get("transcript") or {}).get("segments"):
            transcript_path = os.path.join(job_output_dir, "source_transcript.json")
            with open(transcript_path, "w") as f:
                json.dump(thumb_session["transcript"], f)
            cmd.extend(["--transcript", transcript_path])
    elif upload_slot:
        # Move the pre-uploaded file under the job's name so it is cleaned up
        # with the job like any other upload; the slot is consumed.
        src = upload_slot["path"]
        src_duration = _media_duration_seconds(src)
        if MIN_SOURCE_SECONDS > 0 and 0 < src_duration < MIN_SOURCE_SECONDS:
            shutil.rmtree(job_output_dir, ignore_errors=True)
            _reject_short_source(src_duration)
        input_path = os.path.join(UPLOAD_DIR, f"{job_id}_{upload_slot['filename']}")
        os.replace(src, input_path)
        pending_uploads.pop(upload_id, None)
        cmd.extend(["-i", input_path])
    else:
        # Save uploaded file with size limit check.
        # basename() strips any path components from the client-supplied
        # filename so a name like "../../main.py" can't escape UPLOAD_DIR.
        safe_name = os.path.basename(file.filename or "upload") or "upload"
        input_path = os.path.join(UPLOAD_DIR, f"{job_id}_{safe_name}")

        # Read file in chunks to check size
        size = 0
        limit_bytes = MAX_FILE_SIZE_MB * 1024 * 1024

        async with aiofiles.open(input_path, 'wb') as buffer:
            while content := await file.read(1024 * 1024): # Read 1MB chunks
                size += len(content)
                if size > limit_bytes:
                    os.remove(input_path)
                    shutil.rmtree(job_output_dir)
                    raise HTTPException(status_code=413, detail=f"File too large. Max size {MAX_FILE_SIZE_MB}MB")
                await buffer.write(content)

        upload_duration = _media_duration_seconds(input_path)
        if MIN_SOURCE_SECONDS > 0 and 0 < upload_duration < MIN_SOURCE_SECONDS:
            os.remove(input_path)
            shutil.rmtree(job_output_dir, ignore_errors=True)
            _reject_short_source(upload_duration)

        cmd.extend(["-i", input_path])

    cmd.extend(["-o", job_output_dir])
    if output_format and output_format != "auto":
        cmd.extend(["--format", output_format])

    print(f"[attestation] job={job_id} ip={attestation['ip']} source={attestation['source']} ack=true")

    # Meter + reserve minutes for managed users (no-op for BYOK / self-host).
    user_id, priority, reservation_id, user_plan, partial = await reserve_process_minutes(
        request, url, input_path, job_id, max_minutes=max_minutes)
    if partial:
        # main.py cuts the source down to this many minutes before anything
        # reads it, so the whole pipeline (and the editor) sees a short video.
        env["MAX_SOURCE_MINUTES"] = str(partial["processed_minutes"])
    if user_plan == "free":
        # Free-plan clips carry a burned-in watermark (applied by the main.py
        # subprocess after each clip renders).
        env["WATERMARK"] = "1"

    # Absolute-URL base for the webhook payload: explicit env wins (the API may
    # sit behind a proxy whose forwarded headers we can't trust), else what the
    # caller connected to.
    api_base = os.environ.get("PUBLIC_API_URL", "").rstrip("/") or str(request.base_url).rstrip("/")

    # Compute Hashes and check Idempotency
    from services.idempotency import compute_source_hash, compute_config_hash, find_idempotent_job

    source_hash = await compute_source_hash(url=url, file_path=input_path)
    
    config_dict = {
        "output_format": output_format,
        "layouts": chosen,
        "force_low_quality": force_low,
        "target_clips": n_clips,
        "clip_min_seconds": min_secs,
        "clip_max_seconds": max_secs,
        "auto_hook": env.get("AUTO_HOOK") == "1",
        "auto_hook_style": env.get("AUTO_HOOK_STYLE"),
        "captions": env.get("AUTO_CAPTIONS") != "0",
        "max_minutes": max_minutes,
        "llm_model": req_llm_model,
    }
    config_hash = compute_config_hash(config_dict)
    
    env["SOURCE_HASH"] = source_hash

    existing_job = await find_idempotent_job(source_hash, config_hash)
    if existing_job:
        # Cleanup the just-created files because we will return the existing job
        if not url and not thumb_session and input_path and os.path.exists(input_path):
            try:
                os.remove(input_path)
            except OSError:
                pass
        shutil.rmtree(job_output_dir, ignore_errors=True)
        
        # Determine actual status (use proxy memory logic if needed)
        status = _presented_status(existing_job.id, {"status": existing_job.status})
        return JSONResponse(
            status_code=200,
            content={"job_id": existing_job.id, "status": status, "partial": existing_job.partial},
            headers={"X-Idempotent": "true"}
        )

    # Enqueue Job
    jobs[job_id] = {
        'status': 'queued',
        'logs': [f"Job {job_id} queued."],
        'cmd': cmd,
        'env': env,
        'output_dir': job_output_dir,
        'attestation': attestation,
        'user_id': user_id,
        'reservation_id': reservation_id,
        'watermark': env.get("WATERMARK") == "1",
        'partial': partial,
        'webhook_url': webhook_url,
        'webhook_secret': webhook_secret,
        'base_url': api_base,
        'source_hash': source_hash,
        'config_hash': config_hash,
    }

    # Persist the owner so recovered jobs keep their multi-tenant guard after a
    # restart (see _recover_jobs_from_disk).
    if user_id is not None:
        try:
            os.makedirs(job_output_dir, exist_ok=True)
            with open(os.path.join(job_output_dir, ".owner"), "w") as f:
                f.write(str(user_id))
        except Exception as e:
            print(f"⚠️ Could not persist job owner for {job_id}: {e}")

    # Resume manifest: enough to re-run this job if the container dies mid-flight
    # (a redeploy). No secrets — the env is rebuilt from os.environ on resume.
    _write_resume_manifest(job_id, cmd, priority, user_id, reservation_id,
                           watermark=jobs[job_id]['watermark'],
                           webhook_url=webhook_url, webhook_secret=webhook_secret,
                           base_url=api_base, partial=partial, env=env)

    _enqueue_job(job_id, priority)

    return {"job_id": job_id, "status": "queued", "partial": partial}


def _job_view_from_disk(job_id):
    """What the disk says about a job this instance does not hold in memory.

    During a deploy handover a poll can land on either instance; the one that
    did not accept the job must still answer from the shared directory: a
    metadata JSON means completed (recovered like at startup), a manifest
    means the other instance has it (heartbeat) or will pick it up (queued).
    """
    job_path = os.path.join(OUTPUT_DIR, job_id)
    if not os.path.isdir(job_path):
        return None
    if glob.glob(os.path.join(job_path, "*_metadata.json")):
        _recover_jobs_from_disk()
        return jobs.get(job_id)
    m = _read_manifest(job_id)
    if m is None:
        return None
    alive = time.time() - float(m.get("heartbeat") or 0) < HEARTBEAT_STALE_AFTER
    owner = m.get("user_id")
    return {
        'status': 'processing' if alive else 'queued',
        'logs': ["♻️ The server was updated; your video continues on the new instance."],
        'user_id': (int(owner) if isinstance(owner, str) and owner.isdigit() else owner),
        'result': None,
    }


def _presented_status(job_id, job):
    """A job we hold as 'queued' while draining is really the next instance's:
    if it has started it, say so instead of showing a queue that never moves."""
    if job.get('status') == 'queued' and _draining:
        m = _read_manifest(job_id)
        if m and _manifest_busy_elsewhere(m):
            return 'processing'
    return job['status']


@router.get("/api/status/{job_id}")
async def get_status(job_id: str, request: Request):
    job = jobs.get(job_id)
    if job is None:
        job = _job_view_from_disk(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    await _assert_job_owner(request, job)
    return {
        "status": _presented_status(job_id, job),
        "logs": _visible_logs(job['logs']),
        "result": job.get('result'),
        # Set when only the first part of the source was clipped (quota wall
        # offer), so the dashboard can say so next to the clips.
        "partial": job.get('partial'),
    }


@router.post("/api/jobs/{job_id}/retry")
async def handle_retry_job(job_id: str, request: Request):
    job = jobs.get(job_id)
    if job is None:
        job = _job_view_from_disk(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    await _assert_job_owner(request, job)

    body = {}
    try:
        if request.headers.get("content-type", "").startswith("application/json"):
            body = await request.json()
    except Exception:
        body = {}

    try:
        retried = retry_job(job_id, overrides=body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"job_id": job_id, "status": retried["status"]}


def _locate_source(job_id: str):
    """Find a job's source video on disk, or None.

    Upload jobs keep it in uploads/{job_id}_*; URL jobs keep the download in
    the job dir (--keep-original) under the name recorded as ``source_video``
    in metadata.json. Either way it ages out with the normal retention caps.
    """
    matches = [
        f for f in glob.glob(os.path.join(UPLOAD_DIR, f"{glob.escape(job_id)}_*"))
        if not os.path.basename(f).startswith("thumb_")
    ]
    if matches:
        return matches[0]
    try:
        meta_files = glob.glob(os.path.join(OUTPUT_DIR, job_id, "*_metadata.json"))
        if meta_files:
            with open(meta_files[0], 'r') as f:
                data = json.load(f)
            name = data.get('source_video') if isinstance(data, dict) else None
            if name:
                candidate = os.path.join(OUTPUT_DIR, job_id, os.path.basename(name))
                if os.path.exists(candidate):
                    return candidate
    except Exception:
        pass
    return None


def _source_signature(job_id: str, exp: int) -> str:
    """HMAC tying a job id to an expiry, keyed on the app's JWT secret."""
    secret = (_cloud_config.settings.jwt_secret if BILLING_ENABLED else "") or ""
    msg = f"{job_id}:{exp}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()[:32]


def _job_record(job_id: str):
    """The in-memory job record, or what the shared disk says about it."""
    return jobs.get(job_id) or _job_view_from_disk(job_id)


def _signed_source_url(job_id: str) -> str:
    """The URL to hand a `<video>` tag for this job's source.

    Every place that returns a source URL to the browser must go through here:
    a caller that builds the bare path instead ships a player that cannot
    authenticate, and the clip editor's source monitor 404s in cloud while
    working perfectly in self-host and in every test.
    """
    if not BILLING_ENABLED:
        return f"/api/source/{job_id}"
    exp = int(time.time()) + SOURCE_URL_TTL_SECONDS
    return f"/api/source/{job_id}?exp={exp}&sig={_source_signature(job_id, exp)}"


@router.get("/api/source-url/{job_id}")
async def get_source_url(job_id: str, request: Request):
    """Mint a short-lived signed URL for this job's source video.

    A `<video src>` cannot carry an Authorization header, which is why
    /api/source was left open in the first place. So the owner asks for a
    capability URL here, with the bearer token, and hands the player that.
    """
    record = _job_record(job_id)
    if record is None:
        # No record means no owner to check, and minting anyway would hand out
        # a working key to whoever asked: the one door in this design that
        # gives a capability without asking who you are. A real job resolves
        # here (metadata recovers it, an in-flight one has a manifest naming
        # its owner), so the only callers this turns away are asking about a
        # job that does not exist. Off billing there is nothing to protect and
        # the self-host preview must keep working.
        if BILLING_ENABLED:
            raise HTTPException(status_code=404, detail="Source not found")
    else:
        await _assert_job_owner(request, record)
    return {"url": _signed_source_url(job_id)}


@router.get("/api/source/{job_id}")
async def get_source_video(job_id: str, request: Request,
                           exp: int = 0, sig: str = ""):
    """Stream a job's original source video for the live-analysis preview and
    the clip editor's source monitor.

    Uploaded sources are blob URLs in the browser and don't survive a reload,
    so the recovered session points the preview here instead.

    This one endpoint serves the untouched original, which for a URL job is the
    file we downloaded. Left open it is a public downloader wearing a UUID, so
    a cloud job with an owner needs either a signed URL from /api/source-url or
    a bearer token on the request. Self-host and ownerless BYOK jobs are
    unchanged: there is no owner to check and no secret to sign with.
    """
    signed = (
        BILLING_ENABLED and sig
        and exp > time.time()
        and hmac.compare_digest(sig, _source_signature(job_id, exp))
    )
    # Gated on BILLING_ENABLED, not just on `signed`: _job_record falls through
    # to _job_view_from_disk, which rescans the whole output directory. Off
    # billing there is no owner to find, so that scan would run on every single
    # preview load and buy nothing.
    if not signed and BILLING_ENABLED:
        record = _job_record(job_id)
        if record is not None:
            await _assert_job_owner(request, record)
    source_path = _locate_source(job_id)
    if not source_path:
        raise HTTPException(status_code=404, detail="Source not found")
    return FileResponse(source_path, media_type="video/mp4")


async def _ensure_job_files(job_id: str, request: Request) -> bool:
    job_dir = os.path.join(OUTPUT_DIR, job_id)
    if job_id in jobs and glob.glob(os.path.join(job_dir, "*_metadata.json")):
        return True
    if not BILLING_ENABLED:
        return False
    try:
        await restore_project(job_id, request)
        return True
    except HTTPException:
        return False
    except Exception as e:
        print(f"⚠️  Auto-restore failed for {job_id}: {e}")
        return False


@router.get("/api/jobs/{job_id}/download-all")
async def download_all_clips(job_id: str, request: Request):
    """Bundle the current version of every clip of a job into one ZIP."""
    await _ensure_job_files(job_id, request)
    if job_id in jobs:
        await _assert_job_owner(request, jobs[job_id])

    output_dir = os.path.join(OUTPUT_DIR, job_id)
    json_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))
    if not json_files:
        raise HTTPException(status_code=404, detail="Job not found")

    with open(json_files[0], 'r', encoding='utf-8') as f:
        data = json.load(f)

    # The metadata file on disk never carries video_url — the pipeline doesn't
    # write it, it's injected into the in-memory job record. So prefer the live
    # record (it also tracks edits like subtitled_/hook_ renames) and fall back
    # to the canonical name a job/restore rebuilds, instead of finding nothing.
    base_name = os.path.basename(json_files[0]).replace('_metadata.json', '')
    mem_clips = ((jobs.get(job_id) or {}).get('result') or {}).get('clips') or []

    files = []
    for i, clip in enumerate(data.get('shorts', [])):
        url = None
        if i < len(mem_clips):
            url = (mem_clips[i] or {}).get('video_url')
        url = url or clip.get('video_url')
        filename = (os.path.basename(url.split('/')[-1]) if url
                    else _canonical_clip_file(output_dir, base_name, i))
        path = os.path.join(output_dir, filename)
        if filename and os.path.exists(path):
            files.append((i, path))

    if not files:
        raise HTTPException(status_code=404, detail="No clip files found for this job")

    zip_path = os.path.join(output_dir, f"clips_{int(time.time())}.zip")

    def build_zip():
        # Videos are already compressed; store instead of deflate for speed.
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_STORED) as zf:
            for i, path in files:
                zf.write(path, arcname=f"clip_{i + 1:02d}_{os.path.basename(path)}")

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, build_zip)

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"openshorts_clips_{job_id[:8]}.zip",
        background=BackgroundTask(os.remove, zip_path),
    )


@router.post("/api/projects/{job_id}/restore")
async def restore_project(job_id: str, request: Request):
    if not BILLING_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    from sqlalchemy import select
    from cloud.auth import get_current_user_required
    from cloud.models import Project
    from cloud import database as cloud_db, storage as cloud_storage

    user = await get_current_user_required(request)
    async with cloud_db.session() as s:
        proj = (await s.execute(
            select(Project).where(Project.job_id == job_id)
        )).scalar_one_or_none()
    if proj is None or str(proj.user_id) != str(user.id):
        raise HTTPException(status_code=404, detail="Project not found")

    await _restore_job_files(job_id, proj, str(user.id))
    return {
        "job_id": job_id,
        "status": "completed",
        "result": jobs[job_id]['result'],
        "project_state": proj.state,
        "title": proj.title,
    }


async def _restore_job_files(job_id: str, proj, user_id: str) -> bool:
    """Bring a project's working files back from R2 and register the job.

    The ownership check is the caller's job: ``restore_project`` (the
    endpoint) verifies the session, ``_restore_for_public_path`` serves files
    that are public by job id anyway. Returns True when files were actually
    pulled, False on the idempotent fast path (everything already on disk).
    """
    from cloud import storage as cloud_storage

    pulled = False
    # Per-job lock: a double click must not download the project twice.
    lock = _restore_locks.setdefault(job_id, asyncio.Lock())
    async with lock:
        job_dir = os.path.join(OUTPUT_DIR, job_id)

        # Idempotent fast path: everything the project needs is already on disk.
        needed = {os.path.basename(proj.metadata_r2_key)}
        for c in (proj.state or {}).get("clips", []):
            for k in ("original_file", "server_file"):
                if c.get(k):
                    needed.add(c[k])
        if os.path.isdir(job_dir) and all(
            os.path.exists(os.path.join(job_dir, f)) for f in needed
        ):
            os.utime(job_dir, None)  # restart the retention clock
        else:
            prefix = cloud_storage.job_key(user_id, job_id, "")
            keys = await asyncio.to_thread(cloud_storage.list_keys, prefix)
            if not keys:
                raise HTTPException(status_code=502,
                                    detail="Project files are no longer available")
            # Download into a temp dir first so a partial failure never leaves a
            # half-restored job dir that the fast path would mistake for complete.
            tmp_dir = job_dir + ".restoring"
            shutil.rmtree(tmp_dir, ignore_errors=True)
            os.makedirs(tmp_dir, exist_ok=True)
            sem = asyncio.Semaphore(3)

            async def _download(key):
                fname = os.path.basename(key)
                if not fname:
                    return
                async with sem:
                    await asyncio.to_thread(
                        cloud_storage.download_file, key, os.path.join(tmp_dir, fname))

            try:
                await asyncio.gather(*(_download(k) for k in keys))
            except Exception as e:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                raise HTTPException(status_code=502, detail=f"Restore download failed: {e}")
            # Owner sidecar keeps the multi-tenant guard after a server restart.
            with open(os.path.join(tmp_dir, ".owner"), "w") as f:
                f.write(user_id)
            pulled = True
            if os.path.isdir(job_dir):
                for fname in os.listdir(tmp_dir):
                    shutil.move(os.path.join(tmp_dir, fname), os.path.join(job_dir, fname))
                shutil.rmtree(tmp_dir, ignore_errors=True)
                os.utime(job_dir, None)
            else:
                os.rename(tmp_dir, job_dir)

        # Register (or refresh) the in-memory job — same shape as
        # _recover_jobs_from_disk, so every edit endpoint works unchanged.
        json_files = glob.glob(os.path.join(job_dir, "*_metadata.json"))
        if not json_files:
            raise HTTPException(status_code=502, detail="Project metadata missing")
        data = await read_json_async(json_files[0])
        base_name = os.path.basename(json_files[0]).replace('_metadata.json', '')
        clips = data.get('shorts', [])
        for i, clip in enumerate(clips):
            if not clip.get('video_url'):
                clip['video_url'] = (
                    f"/videos/{job_id}/"
                    f"{_canonical_clip_file(job_dir, base_name, i)}")
        jobs[job_id] = {
            'status': 'completed',
            'logs': ["♻️ Project restored from your library."],
            'output_dir': job_dir,
            'user_id': user_id,
            'result': {'clips': clips, 'cost_analysis': data.get('cost_analysis')},
        }
    if pulled:
        print(f"♻️  Restored {job_id} from the library (working files were gone).")
    return pulled


