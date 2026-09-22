from core.models import *
import os
import llm_backend
import re
import sys
import uuid
import subprocess
import threading
import json
import shutil
import glob
import hashlib
import hmac
import time
import zipfile
import math
import itertools
import functools
import asyncio
import signal
import socket
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
from core.state import jobs, job_queue, concurrency_semaphore, thumbnail_sessions, pending_uploads, MAX_CONCURRENT_JOBS, _enqueue_job
from core.config import (
    UPLOAD_DIR, OUTPUT_DIR, MAX_FILE_SIZE_MB, TIKTOK_POST_MODE,
    OUTPUT_MAX_GB, UPLOADS_MAX_GB, QUALITY_GATE_MIN_HEIGHT, MIN_SOURCE_SECONDS,
    QUALITY_PROBE_SCRIPT, DISABLE_YOUTUBE_URL, BILLING_ENABLED,
    JOB_RETENTION_SECONDS, SOURCE_RETENTION_SECONDS, DEBUG_LOGS
)
import services.job_queue as job_queue_service
from services.job_queue import (
    process_queue, cleanup_jobs, _resume_interrupted_jobs, _recover_jobs_from_disk,
    run_job, _canonical_clip_file, _strip_burned_captions, _strip_burned_hook,
    _reapply_captions, _install_drain_signal_handler, _handover_watch,
    _write_instance_marker, _resume_scan, _purge_local_jobs_for_user,
    enqueue_output, _job_error_text, _sweep_retained_sources, INSTANCE_ID,
    _draining, _running_jobs, _clips_actually_rendered
)

from typing import Any, Dict, Optional, List
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel
from s3_uploader import upload_job_artifacts
import recut
import layout_ranges

load_dotenv()



# Every log line in this module is emoji-prefixed, and a Windows console is
# cp1252 by default. _recover_jobs_from_disk() prints one during startup, so
# without this the server dies before it ever listens:
#
#   UnicodeEncodeError: 'charmap' codec can't encode characters in position 0-1
#   ERROR:    Application startup failed. Exiting.
#
# subtitles._configure_stdio solved this for the transcription path; the server
# needs it too, and needs it before the first print.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# Windows-safe rename: Prevent WinError 183 / WinError 32 on Windows
if sys.platform == "win32":
    _orig_os_rename = os.rename
    def _windows_safe_rename(src, dst, *args, **kwargs):
        last_exc = None
        for attempt in range(15):
            try:
                return os.replace(src, dst)
            except (FileExistsError, PermissionError, OSError) as err:
                last_exc = err
                if attempt >= 5:
                    try:
                        if os.path.isfile(dst):
                            os.remove(dst)
                        return os.replace(src, dst)
                    except Exception:
                        pass
                time.sleep(0.1 * (attempt + 1))
        if last_exc:
            raise last_exc
        return _orig_os_rename(src, dst, *args, **kwargs)

    os.rename = _windows_safe_rename

# ---- Cloud billing (paid / managed-keys) integration --------------------------
# All paid-mode code lives in the optional `cloud/` package and is imported ONLY
# when BILLING_ENABLED is set. With the flag off, the app behaves exactly as the
# self-hosted BYOK app does today (no extra dependencies required).


if BILLING_ENABLED:
    import cloud
    from cloud import managed_keys, metering as _metering, config as _cloud_config, alerts as _alerts
    from cloud.auth import get_current_user_optional
else:
    cloud = None
    managed_keys = None
    _metering = None
    _cloud_config = None
    _alerts = None

    async def get_current_user_optional(request: Request):
        # No-op dependency in self-host mode: every request is anonymous / BYOK.
        return None


async def _user_from_request(request: Request):
    """Load the authenticated cloud user (or None). Cheap indexed lookup."""
    return await get_current_user_optional(request)


async def resolve_gemini(request: Request) -> Optional[str]:
    """Resolve the Gemini API key for a request.

    Cloud (hosted) is PAID-ONLY: there is no BYOK for the core pipeline, so the
    ``X-Gemini-Key`` header is ignored — an entitled user (active plan or trial)
    gets the managed server key, everyone else gets ``None`` (→ 402, start trial).
    Self-host keeps BYOK: header wins, else the env fallback.
    """
    if BILLING_ENABLED:
        user = await _user_from_request(request)
        if managed_keys.has_active_entitlement(user):
            return managed_keys.gemini_key()
        return None
    header = request.headers.get("X-Gemini-Key")
    if header:
        return header
    return os.environ.get("GEMINI_API_KEY")




def gemini_missing_error():
    """The right 4xx when no Gemini key could be resolved.

    402 for a signed-in-but-not-entitled cloud user (needs a plan); 400 otherwise
    (BYOK header simply missing).
    """
    if BILLING_ENABLED:
        return HTTPException(status_code=402, detail={
            "error": "no_plan",
            "message": "This action needs an active plan. Choose a plan or add your own API key.",
        })
    return HTTPException(status_code=400, detail="Missing X-Gemini-Key header")


# Probe rate limiter. In-memory, resets on restart by design — the hard monthly
# quota lives in the metering ledger; this only stops someone hammering the
# proxy with metadata probes.
_probe_times: dict = {}  # user_id -> [monotonic timestamps]
PROBES_PER_HOUR = 15

# Out-of-minutes upsell email: at most one per user per day (a client may
# retry the same 402 many times).
_last_quota_email: dict = {}
_QUOTA_EMAIL_COOLDOWN = 24 * 3600


def _maybe_send_quota_email(user):
    if user is None or user.plan != "free" or not user.email:
        return
    now = time.monotonic()
    last = _last_quota_email.get(str(user.id))
    if last is not None and now - last < _QUOTA_EMAIL_COOLDOWN:
        return
    _last_quota_email[str(user.id)] = now
    from cloud.emails import send_out_of_minutes_email
    upgrade_url = f"{_cloud_config.settings.frontend_url}/#/pricing"
    asyncio.create_task(send_out_of_minutes_email(user.email, upgrade_url))


def _check_probe_rate(user_id):
    now = time.monotonic()
    times = _probe_times.setdefault(str(user_id), [])
    times[:] = [t for t in times if now - t < 3600]
    if len(times) >= PROBES_PER_HOUR:
        raise HTTPException(status_code=429,
                            detail="Too many requests this hour. Please slow down.")
    times.append(now)


def partial_offer(minutes_required: float, minutes_remaining: float) -> int:
    """Minutes of the source we can offer to clip instead of a 402, or 0.

    The offer is the caller's whole remaining balance, floored to full minutes
    (the reservation is in whole minutes), and only when it is both worth
    clipping (``PARTIAL_MIN_MINUTES``) and actually shorter than the source.
    """
    from cloud import config as _cfg  # plain constants; importable with billing off
    offer = int(math.floor(max(0.0, float(minutes_remaining or 0))))
    if offer < _cfg.PARTIAL_MIN_MINUTES or offer >= minutes_required:
        return 0
    return offer


def plan_partial_minutes(minutes_required: int, minutes_remaining: float, max_minutes):
    """How many minutes to reserve for a source of ``minutes_required``.

    Returns ``(reserve, partial)``: ``partial`` is None for a normal whole-video
    job, or ``{"processed_minutes", "total_minutes"}`` when the caller asked
    (``max_minutes``) to clip only the first part. The slice is capped by the
    balance as well as by the request, so a client cannot name a bigger cut
    than it can pay for; when the slice would be too small the request falls
    through to the ordinary quota check (and its 402).
    """
    if max_minutes is None:
        return minutes_required, None
    try:
        asked = float(max_minutes)
    except (TypeError, ValueError):
        return minutes_required, None
    from cloud import config as _cfg
    cap = int(math.floor(min(asked, max(0.0, float(minutes_remaining or 0)))))
    if minutes_required <= cap or cap < _cfg.PARTIAL_MIN_MINUTES:
        return minutes_required, None
    return cap, {"processed_minutes": cap, "total_minutes": minutes_required}


async def reserve_process_minutes(request, url, input_path, job_id, max_minutes=None):
    """Meter a managed /api/process request.

    Returns (user_id, priority, reservation_id, plan, partial).

    ``partial`` is None unless the caller asked (``max_minutes``) to clip only
    the first part of a source its balance cannot cover whole; then it is the
    ``plan_partial_minutes`` dict and only that many minutes are reserved.

    BYOK / self-host requests don't consume minutes (priority 2, no reservation).
    For a managed (entitled, no BYOK header) request this probes the input
    duration, enforces the per-user concurrent-job limit, and reserves minutes —
    raising 402 (quota) or 429 (too many jobs) as needed.

    NOTE: in cloud mode ``resolve_gemini`` ignores ``X-Gemini-Key`` (paid-only,
    no BYOK), so we must NOT skip metering just because that header is present —
    otherwise a client could send a dummy header and run unlimited managed jobs
    on the operator's key for free. Only skip metering when billing is off.
    """
    if not BILLING_ENABLED:
        return None, 2, None, None, None
    user = await _user_from_request(request)
    if not managed_keys.has_active_entitlement(user):
        return None, 2, None, None, None  # shouldn't happen (resolve_gemini would have 402'd)

    priority = _cloud_config.PLAN_PRIORITY.get(user.plan, 1)

    # Per-user simultaneous job cap.
    limit = _cloud_config.PLAN_JOB_LIMIT.get(user.plan, 2)
    active = sum(1 for j in jobs.values()
                 if j.get('user_id') == user.id and j.get('status') in ('queued', 'processing'))
    if active >= limit:
        raise HTTPException(status_code=429,
                            detail="You already have the maximum number of jobs running. Please wait.")

    # Out of minutes -> 402 before probing. The probe is a real yt-dlp metadata
    # fetch through the download proxies, and every job costs at least one
    # minute, so a user at zero can be turned away without spending bandwidth on
    # a duration we are about to reject anyway (4 of 12 submissions in the
    # 21-aug-2026 sample were quota 402s that had already paid for their probe).
    balance = await _metering.get_balance(user.id)
    if balance["remaining"] < 1:
        _maybe_send_quota_email(user)
        raise HTTPException(status_code=402, detail={
            "error": "quota_exceeded",
            "minutes_required": 1,
            "minutes_remaining": balance["remaining"],
            "partial_minutes": 0,
        })

    # Probe rate limit: probing costs a (cheap) proxied metadata call. The
    # 20-minute monthly quota is the real bound on free usage; there is no daily
    # job cap.
    _check_probe_rate(user.id)

    # Probe input duration (blocking → run in a thread). When today's paid
    # traffic is over budget, the probe (and below, the job itself) runs
    # without the per-GB proxy: statics or nothing.
    try:
        from cloud import proxy_ledger as _pl
        paid_allowed = not await _pl.budget_exceeded()
    except Exception:
        pass
    loop = asyncio.get_event_loop()
    try:
        if url:
            minutes = await loop.run_in_executor(
                None, functools.partial(_metering.probe_url_minutes, url,
                                        allow_paid=paid_allowed))
        else:
            minutes = await loop.run_in_executor(None, _metering.probe_file_minutes, input_path)
    except Exception as e:
        from yt_clients import NotASingleVideo
        if isinstance(e, NotASingleVideo):
            raise HTTPException(status_code=400, detail=(
                f"{e} Paste the link of one video (youtube.com/watch?v=... "
                "or youtu.be/...)."))
        raise HTTPException(status_code=400,
                            detail="Could not determine the video duration. Try a different source.")
    finally:
        # A probe that had to reach the paid proxy leaves an event behind;
        # record it (DB row + Telegram) whether or not the probe succeeded.
        try:
            from cloud import proxy_ledger as _pl
            await _pl.drain_probe_events()
        except Exception:
            pass
    minutes = max(1, math.ceil(minutes))

    # A source longer than the balance can be clipped in part instead of
    # refused: the wall offers "the first N minutes" (``partial_minutes`` in
    # the 402 below) and the client resubmits with ``max_minutes``.
    reserve, partial = plan_partial_minutes(minutes, balance["remaining"], max_minutes)
    try:
        reservation_id = await _metering.reserve_minutes(user.id, reserve, job_id)
    except _metering.QuotaExceeded as e:
        _maybe_send_quota_email(user)
        raise HTTPException(status_code=402, detail={
            "error": "quota_exceeded",
            "minutes_required": e.required,
            "minutes_remaining": e.remaining,
            "partial_minutes": partial_offer(e.required, e.remaining),
        })

    return user.id, priority, reservation_id, user.plan, partial


async def reserve_managed_action(request, minutes, job_id, job_type):
    """Reserve quota for a synchronous managed action (e.g. thumbnail image gen).

    Returns a reservation_id to commit/release around the work, or None for
    BYOK / self-host. Raises 402 when the user is out of minutes.
    """
    if not BILLING_ENABLED:
        return None
    if minutes <= 0:
        # Free action (e.g. burning captions). Skip the ledger entirely rather
        # than writing a 0-minute row on every call — the endpoint's own
        # entitlement gate is what bounds it.
        return None
    user = await _user_from_request(request)
    if not managed_keys.has_active_entitlement(user):
        return None  # BYOK header path (self-host) — not metered
    try:
        return await _metering.reserve_minutes(user.id, minutes, job_id, job_type)
    except _metering.QuotaExceeded as e:
        _maybe_send_quota_email(user)
        raise HTTPException(status_code=402, detail={
            "error": "quota_exceeded",
            "minutes_required": e.required,
            "minutes_remaining": e.remaining,
        })


async def require_managed_entitlement(request):
    """Gate a managed compute endpoint that doesn't resolve a Gemini key itself.

    Some endpoints (subtitle/hook FFmpeg re-encodes, render proxy, the thumbnail
    upload that kicks off a YouTube download + Whisper) do expensive server work
    without ever calling ``resolve_gemini``, so nothing was stopping an anonymous
    or non-entitled caller from driving unbounded compute in cloud mode. In cloud
    mode this rejects them with 402; it's a no-op for self-host (BILLING off).
    """
    if not BILLING_ENABLED:
        return None
    user = await _user_from_request(request)
    if not managed_keys.has_active_entitlement(user):
        raise gemini_missing_error()
    return user


async def _owner_id(request):
    """The authenticated cloud user's id to stamp on a new job/session, or None
    for self-host / BYOK / anonymous (BILLING off → nothing to scope)."""
    if not BILLING_ENABLED:
        return None
    user = await _user_from_request(request)
    return user.id if user else None


async def _assert_job_owner(request, record):
    """Cloud multi-tenant guard: reject unless the caller owns this in-memory
    job/session record.

    No-op for self-host (BILLING off) and for records with no owner stamped
    (BYOK / self-host jobs never set ``user_id``). Returns 404 rather than 403 so
    a non-owner can't even confirm the id exists. UUID ids already make these
    stores hard to enumerate; this closes the gap for a shared/leaked id.
    """
    if not BILLING_ENABLED:
        return
    owner = record.get("user_id") if isinstance(record, dict) else None
    if owner is None:
        return
    user = await _user_from_request(request)
    # Compare as strings: live jobs store a uuid.UUID, but jobs recovered from
    # the .owner sidecar store its string form — UUID != str is always True.
    if user is None or str(user.id) != str(owner):
        raise HTTPException(status_code=404, detail="Not found")

# Application State














# --- Mid-flight job resume (survive a redeploy without losing work) ----------
# A job lives only in memory, so killing the container mid-processing used to
# lose it: the user's clip just stops. We persist a tiny manifest per job and,
# on startup, re-enqueue any that were interrupted — the user sees it resume
# instead of vanish. Bounded by MAX_RESUME_ATTEMPTS so a video that reliably
# crashes the worker can't crashloop the service.

# --- Deploy handover (two instances, one disk) -------------------------------
# Coolify starts the NEW container before it stops the old one (rolling
# update), and both see the same OUTPUT_DIR. Without coordination the new one
# re-enqueued, at startup, the very jobs the old one was still rendering —
# and the old one had 30 s to live anyway. Now:
#   * every instance stamps OUTPUT_DIR/.instance with its id at startup; an
#     instance that sees another id there knows it is the OLD one and DRAINS:
#     it finishes what it is running, starts nothing new, and leaves queued
#     manifests for the new instance to pick up;
#   * a running job writes a heartbeat into its manifest every few seconds,
#     so the new instance skips manifests that are alive elsewhere and resumes
#     only the stale ones (an instance killed mid-job stops heartbeating);
#   * SIGTERM also drains, up to DRAIN_TIMEOUT_SECONDS — keep it
#     under the orchestrator stop grace period — before letting uvicorn exit.
# After the jobs are drained, keep SERVING this long with /health/ready at 503
# before closing the socket: the proxy only drops an instance once its
# healthcheck has failed interval*retries times, and closing the socket earlier
# sends that many seconds of requests to a dead port. Measured 2026-08-25: ~60 s
# of alternating 502/200 per deploy with retries=12 and no grace at all.
# Once uvicorn has the signal it closes within --timeout-graceful-shutdown
# (15 s), but the interpreter then waits for non-daemon threads, and a
# request cancelled mid-flight can leave an executor thread stuck in a
# network probe (yt-dlp) for as long as that takes. Seen 2026-08-25: "Finished
# server process" printed, container alive until the 900 s SIGKILL, deploy
# stuck in "Removing old containers". So the process is ended outright a
# little after uvicorn was told to stop. Jobs are already drained by then.
                                     # proxy stops routing here before the
                                     # listening socket closes
_running_jobs: set = set()           # job ids with a live subprocess here












































# Monthly proxy bandwidth counter (in-memory; an alert threshold, not a bill —
# losing it on a deploy just means the alert re-arms from 0 mid-month).
















# Markers that identify a line as an actual error rather than progress noise.
# "Error:" (capital E) catches raised exception lines — RuntimeError:,
# DownloadError:, GeminiBlockedError: — which "ERROR:" alone missed, leaving
# alerts with a bare "Traceback ... exit code 1" and no cause (prod 20-ago).








# --- Job completion webhooks --------------------------------------------------
# Agents and pipelines (n8n, cron, MCP clients) need push, not poll: a caller
# passes webhook_url on /api/process and gets one POST when the job reaches a
# terminal state. The URL goes through assert_public_url both at submit and at
# delivery time — the second check is what defeats DNS rebinding between them.

















@asynccontextmanager
async def lifespan(app: FastAPI):
    # Rehydrate finished jobs from disk before serving (survives restarts).
    _recover_jobs_from_disk()
    # Re-enqueue jobs that were mid-processing when we stopped (redeploy). Their
    # reservations must survive the orphan sweep so the resumed run can settle them.
    _resumed_reservation_ids = _resume_interrupted_jobs()
    # Deploy handover: claim the marker (any older instance sees it and drains),
    # keep watching it in case a newer one appears, keep looking for manifests
    # left behind, and drain instead of dying on SIGTERM.
    _write_instance_marker()
    _install_drain_signal_handler()
    asyncio.create_task(_handover_watch())
    asyncio.create_task(_resume_scan())
    # Start worker and cleanup
    worker_task = asyncio.create_task(process_queue())
    cleanup_task = asyncio.create_task(cleanup_jobs())
    from services.webhook import start_webhook_worker, stop_webhook_worker
    start_webhook_worker()
    if BILLING_ENABLED:
        await cloud.setup_async(app, keep_reservation_ids=_resumed_reservation_ids)
        # Account erasure lives in cloud/, which can't import app.py; hand it the
        # one thing only this module can do — wipe the local working files.
        cloud.account.register_local_purge(_purge_local_jobs_for_user)
        # Nag on Telegram while the residential proxy is down/out of credits —
        # a single job-failure alert is easy to miss and ingest stays broken
        # until someone tops the balance up.
        asyncio.create_task(_alerts.proxy_watch_loop())
    yield
    # Cleanup (optional: cancel worker)
    await stop_webhook_worker()

app = FastAPI(lifespan=lifespan)

# Cloud mode: attach middleware + routers at import time (before the app serves).
if BILLING_ENABLED:
    cloud.setup_sync(app)

# MCP server (/mcp): the pipeline as agent-callable tools. Works in both modes —
# cloud requires an osk_ API key, self-host keeps BYOK (see mcp_server.py).
import mcp_server as _mcp_server


# Enable CORS for frontend. Cloud mode locks this down to the configured origins;
# self-host keeps the permissive wildcard it has always used.
app.add_middleware(
    CORSMiddleware,
    allow_origins=cloud.settings.allowed_origins if BILLING_ENABLED else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Without this the browser hides them from fetch(), so the clip download had
    # no total to measure against and could not show progress. Safelisted or not,
    # they only become readable to JS once they are named here.
    expose_headers=["Content-Length", "Content-Range", "Accept-Ranges"],
)

# Mount static files for serving videos. A miss under /videos/<job_id>/ first
# tries to bring the job back from R2 (see restoring_static.py): the players
# of a reopened project used to 404 while the transcript requests were still
# restoring it. Late-bound lambda: the restorer is defined further down.
from restoring_static import RestoringStaticFiles
import media_auth
app.mount("/videos", RestoringStaticFiles(
    directory=OUTPUT_DIR,
    guard=media_auth.is_servable,
    restorer=lambda job_id: _restore_for_public_path(job_id)), name="videos")

# Mount static files for serving thumbnails
THUMBNAILS_DIR = os.path.join(OUTPUT_DIR, "thumbnails")
os.makedirs(THUMBNAILS_DIR, exist_ok=True)
app.mount("/thumbnails", StaticFiles(directory=THUMBNAILS_DIR), name="thumbnails")


def _safe_under(base_dir: str, user_rel_path: str) -> Optional[str]:
    """Resolve ``user_rel_path`` under ``base_dir`` and reject path traversal.

    Returns the absolute path only if it stays inside ``base_dir`` (after
    following ``..``); otherwise None. Used to sanitize client-supplied file
    references so ``../../.env`` can't escape the output directories.
    """
    base = os.path.realpath(base_dir)
    target = os.path.realpath(os.path.join(base, user_rel_path))
    if target == base or target.startswith(base + os.sep):
        return target
    return None

# Masks user:password credentials embedded in any URL (e.g. the residential
# proxy URL that yt-dlp echoes in its verbose debug output) before the line is
# ever printed to the server console or stored in the job log.




# Cloud users don't need (and shouldn't see) implementation details: the ingest
# plumbing (proxy / downloader / cookies) OR which AI model powers it, token
# usage and cost. These are dropped from the client view even when the line is
# emoji-prefixed. Never applied under DEBUG_LOGS (local dev sees everything).






@app.get("/health")
async def health():
    """Lightweight liveness probe for uptime monitoring."""
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    """Readiness probe. Reverse proxies drop an instance from the load
    balancer as soon as it turns unhealthy, so answering 503 from the moment
    SIGTERM arrives pulls this instance out of rotation while it can still
    serve, instead of after its socket is gone. Only SIGTERM flips it: a drain
    triggered by the instance marker starts while the new instance is still
    booting, and going unready then would leave nobody routable."""
    if job_queue_service._stopping:
        return JSONResponse({"status": "stopping"}, status_code=503)
    return {"status": "ready"}

@app.get("/api/config")
async def get_config():
    return {
        "youtubeUrlEnabled": not DISABLE_YOUTUBE_URL,
        "billingEnabled": BILLING_ENABLED,
        "googleAuthEnabled": bool(BILLING_ENABLED and cloud.settings.google_auth_enabled),
        "jobRetentionSeconds": JOB_RETENTION_SECONDS,
        # Self-host only: tells the dashboard the Gemini key is optional
        # because the moment picker runs on an OpenAI-compatible server.
        "localLlm": None if BILLING_ENABLED else llm_backend.describe(),
    }







# Layouts the caller can let the renderer choose from, mapped to the env var
# each one is gated on. The renderer only ever picks between layouts that are
# switched on here.
#
# This is opt-in per job, not a detector running on every video, because the
# detection is not good enough to be trusted unprompted: measured over the
# 48-clip corpus, routing every video through the on-screen-content check fixed
# 13 clips and spoiled 13 others (talking heads and corner tickers demoted to a
# layout they do not need). Asking the person who knows what they uploaded costs
# them one click and removes that whole class of error. It is also what OpusClip
# does — its "applicable auto layout" panel lets the user pick which layouts the
# AI may apply.
LAYOUT_ENV = {
    "split": "SPLIT_LAYOUT",          # two speakers stacked
    "screencast": "SCREENCAST_LAYOUT",  # slides/screen share over the speaker
    "speaker_cut": "SPEAKER_CUT",     # hard cuts to whoever is talking
    "punch_in": "PUNCH_IN",           # small push on the clip's beats
}

# Stacking and cutting both need to know who is speaking.
LAYOUT_IMPLIES = {
    "split": ["SPEAKER_SIGNAL"],
    "speaker_cut": ["SPEAKER_SIGNAL"],
}


# --------------------------------------------------------------------------- #
# Agent uploads: a two-step path for callers that hold a video FILE, not a URL
# (an MCP client handed the file by the user). POST reserves an id and returns
# a PUT URL; the client streams the raw bytes there with no auth beyond the
# unguessable id (so `curl -T` works from any agent runtime); /api/process then
# takes the upload_id. Files live in UPLOAD_DIR under the same retention sweep
# as every other source upload, and the owner recorded at POST is checked at
# process time so a leaked id cannot start a job on someone else's account.
# --------------------------------------------------------------------------- #
pending_uploads: Dict[str, Dict] = {}
# Unconsumed slots are gone after this; a consumed one becomes the job's
# input and follows the job's own retention instead.
UPLOAD_TTL_SECONDS = int(os.environ.get("UPLOAD_TTL_SECONDS", str(6 * 3600)))

























# How long a signed source URL stays valid. Long enough to survive an editing
# session and a page reload, short enough that a link leaked through a log, a
# referer or a shared screenshot is dead by the time anyone tries it.
SOURCE_URL_TTL_SECONDS = int(os.environ.get("SOURCE_URL_TTL_SECONDS", "21600"))














# --- Project restore (paid mode) --------------------------------------------
# Re-hydrates an archived project from R2 back into output/{job_id}/ so every
# edit endpoint works on it again. Restored files land with a fresh mtime, so
# the retention clock restarts; re-restoring after a purge is cheap.
_restore_locks: Dict[str, asyncio.Lock] = {}
# Job ids are uuid4 strings; anything else under /videos is not a job dir
# (thumbnails, stray probes) and must not reach the database.
_JOB_ID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')






async def _restore_for_public_path(job_id: str) -> bool:
    """Restorer for the /videos mount: a miss under /videos/<job_id>/ pulls
    the project back from R2 for its owner, without a session. Those files
    are public by job id already (the mount has no auth), so this grants
    nothing new; it only stops a reopened project's players from 404ing
    while the API side is still restoring it. True means "look again".
    """
    if not BILLING_ENABLED or not _JOB_ID_RE.match(job_id or ""):
        return False
    from sqlalchemy import select
    from cloud.models import Project
    from cloud import database as cloud_db
    async with cloud_db.session() as s:
        proj = (await s.execute(
            select(Project).where(Project.job_id == job_id)
        )).scalar_one_or_none()
    if proj is None:
        return False
    try:
        await _restore_job_files(job_id, proj, str(proj.user_id))
    except HTTPException as e:
        print(f"⚠️  /videos restore of {job_id} failed: {e.detail}")
        return False
    except Exception as e:
        print(f"⚠️  /videos restore of {job_id} failed: {e}")
        return False
    return True


async def _ensure_job_files(job_id: str, request: Request) -> bool:
    """Make a completed job usable again after its working files vanished.

    OUTPUT_DIR is not durable — a container restart or redeploy wipes it — so
    endpoints that read a job's files would 404 on a project the user can still
    see in their library. Pull it back from R2 on demand (same path as the
    explicit /restore), so editing keeps working instead of dead-ending.

    Returns True when the job is available afterwards. Never raises: callers
    keep their own 404s for jobs that genuinely don't exist.
    """
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


from editor import VideoEditor
from subtitles import generate_srt, generate_ass, burn_subtitles, generate_srt_from_video
from hooks import add_hook_to_video
from thumbnail import (analyze_video_for_titles, refine_titles, generate_thumbnail,
                       generate_youtube_description, extract_face_frames)

# --- Clip editor: EDL + re-render ---

# The editor ships the WHOLE source transcript, not a window around the clip:
# the point of the source track is extending a cut into material the clip never
# covered, and you cannot pick a new in-point from words you were not sent.
# Cost is about 7 KB of JSON per minute of speech, fetched once per editor open.








# Manual framing -> reframe-engine strategy. 'full' shows the whole source
# frame (WIDE: no side-cropping, blurred filler bands); 'track' forces the
# subject-tracking crop. Anything non-auto needs the retained source video.
_FRAMING_STRATEGIES = {"auto": None, "full": "WIDE", "track": "TRACK"}


# One lock per job (same pattern as _restore_locks): rerenders on the same job
# share metadata.json and the canonical files, so they must not interleave.
_rerender_locks: Dict[str, asyncio.Lock] = {}

# Scene-listing builds write stable preview/thumbnail names per job; serialize
# them so overlapping editor opens don't tear each other's files.
_scenes_locks: Dict[str, asyncio.Lock] = {}






# --- Manual framing -----------------------------------------------------------
#
# The reframe engine picks the crop automatically, and on a podcast it is right
# most of the time and grossly wrong occasionally: a wide shot of the whole
# table averages over one face, so the scene falls to GENERAL (letterboxed) or
# tracks the wrong person. There was no way to say "no, frame it here".
#
# The unit is the SCENE, not the clip, because a podcast cuts between a fixed
# close camera and a fixed wide one, and the right crop differs per camera.
# Scene boundaries already are the camera changes: PySceneDetect finds them.
#
# Scenes the user never touches keep the automatic camera, so correcting one
# bad shot cannot spoil the ones the tracker got right.

# --- Remotion Render Proxy ---
RENDER_SERVICE_URL = os.getenv("RENDER_SERVICE_URL", "http://renderer:3100")




app.include_router(_mcp_server.router)
from routes.thumbnails import router as thumbnails_router
from routes.clips import router as clips_router
from routes.process import router as process_router
app.include_router(thumbnails_router)
app.include_router(clips_router)
app.include_router(process_router)
from routes.process import (
    _probe_youtube_quality, _media_duration_seconds, _source_signature,
    _signed_source_url, _presented_status, layout_env
)
