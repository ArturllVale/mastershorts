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
    _write_instance_marker, _resume_scan, _purge_local_jobs_for_user
)

from typing import Any, Dict, Optional, List
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel
from s3_uploader import upload_job_artifacts, list_all_clips, upload_actor_to_s3, list_actor_gallery, upload_video_to_gallery, list_video_gallery
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


async def resolve_upload_post(request: Request, body_key: Optional[str] = None):
    """Resolve the Upload-Post key and the profile to post as.

    Returns ``(api_key, forced_profile_username_or_None)``. Cloud is paid-only:
    an entitled user gets the managed key + their own forced profile (body key /
    user_id ignored); a non-entitled user gets ``(None, None)``. Self-host keeps
    BYOK: header, then body key, then env.
    """
    if BILLING_ENABLED:
        user = await _user_from_request(request)
        if managed_keys.has_active_entitlement(user):
            profile = await cloud.social_profiles.ensure_profile(user)
            return managed_keys.upload_post_key(), profile
        return None, None
    header = request.headers.get("X-Upload-Post-Key")
    key = header or body_key or os.environ.get("UPLOAD_POST_API_KEY")
    return key, None


def resolve_post_profile(forced_profile: Optional[str], client_profile: Optional[str]) -> str:
    """The Upload-Post profile to act as, for posting/scheduling/analytics.

    Fails closed on purpose. Every call site used to read
    ``forced_profile or client_profile``, which quietly honours whatever
    profile the *client* asked for if the server ever failed to resolve its
    own — one refactor of ``resolve_upload_post`` away from letting a cloud
    user schedule into someone else's connected accounts. In cloud mode the
    client value is never consulted: either the server knows the caller's
    profile or the request is refused.
    """
    if BILLING_ENABLED:
        if not forced_profile:
            raise HTTPException(
                status_code=503,
                detail="Could not resolve your social profile. Please try again.")
        return forced_profile
    # Self-host: no user model, the caller owns the Upload-Post account whose
    # key resolved above, so it picks its own profile.
    profile = forced_profile or client_profile
    if not profile:
        raise HTTPException(status_code=400, detail="Missing Upload-Post user profile")
    return profile


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




import httpx

@app.post("/api/social/post")
async def post_to_socials(req: SocialPostRequest, request: Request):
    await _ensure_job_files(req.job_id, request)
    if req.job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    # Resolve the Upload-Post key + profile. For managed users the server key is
    # used and their own profile is forced (body api_key / user_id are ignored).
    upload_key, forced_profile = await resolve_upload_post(request, req.api_key)
    if not upload_key:
        raise HTTPException(status_code=400, detail="Missing Upload-Post API key")
    post_user = resolve_post_profile(forced_profile, req.user_id)

    job = jobs[req.job_id]
    await _assert_job_owner(request, job)
    if 'result' not in job or 'clips' not in job['result']:
        raise HTTPException(status_code=400, detail="Job result not available")

    try:
        clip = job['result']['clips'][req.clip_index]
        # Video URL is relative /videos/..., we need absolute file path
        # clip['video_url'] is like "/videos/{job_id}/{filename}"
        # We constructed it as: f"/videos/{job_id}/{clip_filename}"
        # And file is at f"{OUTPUT_DIR}/{job_id}/{clip_filename}"
        
        filename = clip['video_url'].split('/')[-1]
        file_path = os.path.join(OUTPUT_DIR, req.job_id, filename)
        
        if not os.path.exists(file_path):
             raise HTTPException(status_code=404, detail=f"Video file not found: {file_path}")

        # Construct parameters for Upload-Post API
        # Fallbacks
        final_title = req.title or clip.get('title', 'Viral Short')
        final_description = req.description or clip.get('video_description_for_instagram') or clip.get('video_description_for_tiktok') or "Check this out!"
        
        # Prepare form data
        url = "https://api.upload-post.com/api/upload"
        headers = {
            "Authorization": f"Apikey {upload_key}"
        }

        # Prepare data as dict (httpx handles lists for multiple values)
        data_payload = {
            "user": post_user,
            "title": final_title,
            "platform[]": req.platforms, # Pass list directly
            "async_upload": "true"  # Enable async upload
        }

        # Add scheduling if present
        if req.scheduled_date:
            data_payload["scheduled_date"] = req.scheduled_date
            if req.timezone:
                data_payload["timezone"] = req.timezone
        
        # Add Platform specifics
        if "tiktok" in req.platforms:
             data_payload["tiktok_title"] = final_description
             data_payload["post_mode"] = TIKTOK_POST_MODE
             
        if "instagram" in req.platforms:
             data_payload["instagram_title"] = final_description
             data_payload["media_type"] = "REELS"

        if "youtube" in req.platforms:
             yt_title = req.title or clip.get('video_title_for_youtube_short', final_title)
             data_payload["youtube_title"] = yt_title
             data_payload["youtube_description"] = final_description
             data_payload["privacyStatus"] = "public"

        # Send File
        # httpx AsyncClient requires async file reading or bytes. 
        # Since we have MAX_FILE_SIZE_MB, reading into memory is safe-ish.
        with open(file_path, "rb") as f:
            file_content = f.read()
            
        files = {
            "video": (filename, file_content, "video/mp4")
        }

        # Switch to synchronous Client to avoid "sync request with AsyncClient" error with multipart/files
        with httpx.Client(timeout=120.0) as client:
            print(f"📡 Sending to Upload-Post for platforms: {req.platforms}")
            response = client.post(url, headers=headers, data=data_payload, files=files)
            
        if response.status_code not in [200, 201, 202]: # Added 201
             print(f"❌ Upload-Post Error: {response.text}")
             raise HTTPException(status_code=response.status_code, detail=f"Vendor API Error: {response.text}")

        return response.json()

    except Exception as e:
        print(f"❌ Social Post Exception: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/social/user")
async def get_social_user(request: Request):
    """Proxy to fetch user profiles from Upload-Post.

    BYOK: uses the caller's key and returns all profiles on that account.
    Managed: uses the server key but returns ONLY the caller's own profile.
    """
    api_key, forced_profile = await resolve_upload_post(request, None)
    if not api_key:
         raise HTTPException(status_code=400, detail="Missing X-Upload-Post-Key header")

    url = "https://api.upload-post.com/api/uploadposts/users"
    print(f"🔍 Fetching User ID from: {url}")
    headers = {"Authorization": f"Apikey {api_key}"}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                print(f"❌ Upload-Post User Fetch Error: {resp.text}")
                raise HTTPException(status_code=resp.status_code, detail=f"Failed to fetch user: {resp.text}")
            
            data = resp.json()
            print(f"🔍 Upload-Post User Response: {data}")
            
            user_id = None
            # The structure is {'success': True, 'profiles': [{'username': '...'}, ...]}
            profiles_list = []
            if isinstance(data, dict):
                 raw_profiles = data.get('profiles', [])
                 if isinstance(raw_profiles, list):
                     for p in raw_profiles:
                         username = p.get('username')
                         if username:
                             # Determine connected platforms
                             socials = p.get('social_accounts', {})
                             connected = []
                             # Check typical platforms
                             for platform in ['tiktok', 'instagram', 'youtube']:
                                 account_info = socials.get(platform)
                                 # If it's a dict and typically has data, or just not empty string
                                 if isinstance(account_info, dict):
                                     connected.append(platform)
                             
                             profiles_list.append({
                                 "username": username,
                                 "connected": connected
                             })
            
            # Managed users must only ever see their own profile.
            if forced_profile is not None:
                profiles_list = [p for p in profiles_list if p.get("username") == forced_profile]

            if not profiles_list:
                # Fallback if no profiles found
                return {"profiles": [], "error": "No profiles found"}

            return {"profiles": profiles_list}
            
            
        except Exception as e:
             raise HTTPException(status_code=500, detail=str(e))


# --- Social analytics (thin proxies over Upload-Post) ---
# Read-only mirrors of the posting flow above: managed users are locked to their
# own profile (the body/query profile is ignored), BYOK callers bring their own
# key and pick the profile with ?user=.

# Separate bucket from _probe_times: analytics polling must not eat into the
# metering-probe allowance, and vice versa. Protects the managed Upload-Post
# key's vendor rate limits from a runaway polling loop.
_analytics_times: dict = {}  # user_id -> [monotonic timestamps]
ANALYTICS_PER_HOUR = 60


def _check_analytics_rate(user_id):
    now = time.monotonic()
    times = _analytics_times.setdefault(str(user_id), [])
    times[:] = [t for t in times if now - t < 3600]
    if len(times) >= ANALYTICS_PER_HOUR:
        raise HTTPException(status_code=429,
                            detail="Too many analytics requests this hour. Please slow down.")
    times.append(now)


async def _social_analytics_auth(request: Request, byok_profile: Optional[str]):
    api_key, forced_profile = await resolve_upload_post(request, None)
    if not api_key:
        if BILLING_ENABLED:
            # Signed-in free user (or no auth at all): social posting is
            # paid-only in cloud, so there are no posts to measure either.
            raise HTTPException(status_code=402, detail={
                "error": "no_plan",
                "message": "Social analytics needs an active plan.",
            })
        raise HTTPException(status_code=400, detail="Missing X-Upload-Post-Key header")
    if forced_profile:
        user = await _user_from_request(request)
        if user:
            _check_analytics_rate(user.id)
    return api_key, resolve_post_profile(forced_profile, byok_profile)


async def _upload_post_get(api_key: str, url: str, params: dict):
    headers = {"Authorization": f"Apikey {api_key}"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"Vendor API Error: {resp.text}")
    return resp.json()


@app.get("/api/social/analytics")
async def social_profile_analytics(
    request: Request,
    platforms: str = "tiktok,instagram,youtube",
    user: Optional[str] = None,
):
    """Aggregated profile analytics: followers, views, engagement per platform."""
    api_key, profile = await _social_analytics_auth(request, user)
    return await _upload_post_get(
        api_key,
        f"https://api.upload-post.com/api/analytics/{profile}",
        {"platforms": platforms},
    )


@app.get("/api/social/analytics/posts")
async def social_post_analytics(
    request: Request,
    platform: Optional[str] = None,
    limit: Optional[int] = None,
    cursor: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    user: Optional[str] = None,
):
    """Per-post metrics for the profile's published posts (Upload-Post cache)."""
    api_key, profile = await _social_analytics_auth(request, user)
    params = {"user": profile}
    for key, value in (("platform", platform), ("limit", limit),
                       ("cursor", cursor), ("since", since), ("until", until)):
        if value is not None:
            params[key] = value
    return await _upload_post_get(
        api_key,
        "https://api.upload-post.com/api/uploadposts/post-analytics/cached",
        params,
    )


_PERIOD_DAYS = {"last_day": 1, "last_week": 7, "last_month": 30,
                "last_3months": 90, "last_year": 365}


def _post_row_views(row: dict) -> float:
    metrics = row.get("post_metrics") or row.get("metrics") or row
    for key in ("views", "impressions", "plays"):
        value = metrics.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0
    return 0.0


@app.get("/api/social/analytics/impressions")
async def social_total_impressions(
    request: Request,
    period: Optional[str] = None,     # last_day | last_week | last_month | last_3months | last_year
    start_date: Optional[str] = None,  # YYYY-MM-DD
    end_date: Optional[str] = None,
    platform: Optional[str] = None,
    breakdown: Optional[bool] = None,
    user: Optional[str] = None,
):
    """Total impressions for the profile over a window.

    Computed by aggregating the profile-scoped post cache instead of proxying
    Upload-Post's /total-impressions: that endpoint echoes the requested
    profile but returns account-wide numbers (observed 2026-08-21 — a profile
    with zero posts got 85K Instagram impressions), which for managed users
    would leak other tenants' aggregates. The cache endpoint IS scoped by
    ?user=, so summing it is both correct and cheap.
    """
    api_key, profile = await _social_analytics_auth(request, user)

    days = _PERIOD_DAYS.get(period or "", 30)
    since = start_date or (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    params = {"user": profile, "since": since, "limit": 200}
    if end_date:
        params["until"] = end_date
    if platform:
        params["platform"] = platform

    total = 0.0
    per_platform: dict = {}
    for _page in range(5):  # 1000 posts is far beyond any real profile window
        data = await _upload_post_get(
            api_key,
            "https://api.upload-post.com/api/uploadposts/post-analytics/cached",
            params,
        )
        rows = data.get("posts") or data.get("data") or data.get("items") or []
        for row in rows:
            if not isinstance(row, dict):
                continue
            views = _post_row_views(row)
            total += views
            name = row.get("platform")
            if name:
                per_platform[name] = per_platform.get(name, 0) + views
        cursor = data.get("next_cursor")
        if not cursor or not data.get("has_more"):
            break
        params["cursor"] = cursor

    result = {
        "profile_username": profile,
        "total_impressions": round(total),
        "per_platform": {k: round(v) for k, v in per_platform.items()},
    }
    return result


async def _scheduled_posts_for(api_key: str, profile: str) -> list:
    """The caller's pending scheduled posts.

    Upload-Post's GET /uploadposts/schedule takes no profile filter and returns
    everything the *account* has pending — with the managed key that is every
    OpenShorts user's queue, so the filter below is what keeps one tenant from
    seeing (or cancelling) another's. Same class of bug as the impressions
    endpoint; do not "simplify" it away.
    """
    data = await _upload_post_get(
        api_key, "https://api.upload-post.com/api/uploadposts/schedule", {})
    rows = data.get("scheduled_posts") or data.get("data") or []
    return [r for r in rows
            if isinstance(r, dict) and r.get("profile_username") == profile]


@app.get("/api/social/scheduled")
async def social_scheduled(request: Request, user: Optional[str] = None):
    """Pending scheduled posts for the caller's profile, soonest first."""
    api_key, profile = await _social_analytics_auth(request, user)
    rows = await _scheduled_posts_for(api_key, profile)
    rows.sort(key=lambda r: r.get("scheduled_date") or "")
    return {"profile_username": profile, "scheduled_posts": rows}


@app.delete("/api/social/scheduled/{job_id}")
async def social_cancel_scheduled(job_id: str, request: Request, user: Optional[str] = None):
    """Cancel one pending scheduled post, if it belongs to the caller."""
    api_key, profile = await _social_analytics_auth(request, user)
    rows = await _scheduled_posts_for(api_key, profile)
    if not any(r.get("job_id") == job_id for r in rows):
        # 404 rather than 403: never confirm that someone else's job exists.
        raise HTTPException(status_code=404, detail="Scheduled post not found")
    headers = {"Authorization": f"Apikey {api_key}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(
            f"https://api.upload-post.com/api/uploadposts/schedule/{job_id}",
            headers=headers)
    if resp.status_code not in (200, 202, 204):
        raise HTTPException(status_code=resp.status_code,
                            detail=f"Vendor API Error: {resp.text}")
    return {"success": True, "job_id": job_id}


# --- Thumbnail Studio Endpoints ---





# @app.get("/api/gallery/clips")
# async def get_gallery_clips(limit: int = 20, offset: int = 0, refresh: bool = False):
#     """
#     Fetch clips from S3 for the gallery with pagination.
#
#     Args:
#         limit: Number of clips to return (default 20, max 100)
#         offset: Starting position for pagination
#         refresh: Force refresh cache
#     """
#     try:
#         # Clamp limit to reasonable values
#         limit = min(max(1, limit), 100)
#
#         # Get clips (uses cache internally)
#         all_clips = list_all_clips(limit=limit + offset, force_refresh=refresh)
#
#         # Apply offset for pagination
#         clips = all_clips[offset:offset + limit]
#
#         return {
#             "clips": clips,
#             "total": len(all_clips),
#             "limit": limit,
#             "offset": offset,
#             "has_more": len(all_clips) > offset + limit
#         }
#     except Exception as e:
#         print(f"❌ Gallery Error: {e}")
#         raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# SaaSShorts: AI UGC Video Generator for SaaS Products
# ═══════════════════════════════════════════════════════════════════════


# State for SaaSShorts jobs (separate from video processing jobs)


# The gallery and the per-video pages are rendered by this API service, but the
# app they advertise lives on www. A relative href on `api.` host resolves
# against `api.`, where `/` is not the app (it is a 404), so every link that
# crosses hosts is written absolute. `www.openshorts.app/gallery` and
# `/video/...` 301 to the api host (dashboard/nginx.conf), so the api host is
# the final domain for those two and the app host is final for everything else.
APP_HOST = "https://www.openshorts.app"
GALLERY_HOST = "https://api.openshorts.app"


def _json_ld(payload: dict) -> str:
    """Serialise a JSON-LD payload for an inline <script> block.

    `html.escape()` is the wrong tool here: inside JSON-LD it produces
    `&amp;quot;` and friends, which is still valid JSON *text* but no longer
    means what it said, so the crawler reads a literal entity instead of a
    quote. The right escaping for this context is JSON's own, plus `<>` and `&`
    as unicode escapes so a title can never close the script tag.
    """
    return (
        json.dumps(payload, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


@app.get("/gallery", response_class=HTMLResponse)
async def gallery_html_page():
    """SEO gallery page with all generated UGC videos."""
    import html as html_mod
    loop = asyncio.get_running_loop()
    videos = await loop.run_in_executor(None, list_video_gallery, 100)

    cards_html = ""
    ld_items = []
    for i, v in enumerate(videos):
        # Two versions of the same string on purpose: the HTML one is escaped
        # for markup, the JSON-LD one is serialised as JSON. Escaping once and
        # reusing the result in both places is what produced `&amp;amp;`.
        raw_title = v.get("title", "Untitled")
        title = html_mod.escape(raw_title)
        video_url = v.get("video_url", "")
        actor_url = v.get("actor_url", "")
        video_id = v.get("video_id", "")
        duration = v.get("duration", 0)
        mode = v.get("video_mode", "")
        product = html_mod.escape(v.get("product_name", ""))
        caption = html_mod.escape(v.get("caption", "")[:120])

        mode_badge = '<span style="background:#22c55e;color:#000;padding:2px 8px;border-radius:9999px;font-size:10px;font-weight:700">LOW COST</span>' if mode == "lowcost" else '<span style="background:#8b5cf6;color:#fff;padding:2px 8px;border-radius:9999px;font-size:10px;font-weight:700">PREMIUM</span>'

        cards_html += f'''
        <a href="/video/{video_id}" style="text-decoration:none;color:inherit">
          <div style="background:#18181b;border-radius:16px;overflow:hidden;border:1px solid #27272a;transition:transform 0.2s" onmouseover="this.style.transform='scale(1.02)'" onmouseout="this.style.transform='scale(1)'">
            <div style="position:relative;aspect-ratio:9/16;background:#000">
              <video src="{video_url}" poster="{actor_url}" muted playsinline preload="metadata"
                     onmouseenter="this.play()" onmouseleave="this.pause();this.currentTime=0"
                     style="width:100%;height:100%;object-fit:cover"></video>
              <div style="position:absolute;top:8px;right:8px">{mode_badge}</div>
            </div>
            <div style="padding:12px">
              <h2 style="font-size:14px;font-weight:600;margin:0 0 4px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{title}</h2>
              <p style="font-size:11px;color:#71717a;margin:0">{duration:.0f}s · {product}</p>
            </div>
          </div>
        </a>'''

        ld_items.append(
            {
                "@type": "ListItem",
                "position": i + 1,
                # The apex 301s to www, which 301s to here: name the host the
                # page is actually served from.
                "url": f"{GALLERY_HOST}/video/{video_id}",
                "name": raw_title,
            }
        )

    ld_json = _json_ld(
        {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": "AI UGC Video Gallery",
            "mainEntity": {
                "@type": "ItemList",
                "numberOfItems": len(videos),
                "itemListElement": ld_items,
            },
        }
    )

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI UGC Video Gallery | OpenShorts</title>
<meta name="description" content="Browse {len(videos)} AI-generated UGC marketing videos. Create viral TikTok and Instagram Reels for your SaaS product.">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{GALLERY_HOST}/gallery">
<meta property="og:title" content="AI UGC Video Gallery | OpenShorts">
<meta property="og:type" content="website">
<meta property="og:description" content="Browse AI-generated UGC marketing videos for SaaS products.">
<script type="application/ld+json">{ld_json}</script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0a0a0c;color:#e4e4e7;font-family:-apple-system,BlinkMacSystemFont,sans-serif}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:20px;padding:20px;max-width:1400px;margin:0 auto}}
nav{{padding:20px 40px;border-bottom:1px solid #27272a;display:flex;align-items:center;justify-content:space-between}}
h1{{font-size:28px;font-weight:700;padding:40px 20px 0;text-align:center}}
.subtitle{{text-align:center;color:#71717a;font-size:14px;padding:8px 20px 20px}}
.cta{{display:inline-block;background:#8b5cf6;color:#fff;padding:10px 24px;border-radius:12px;text-decoration:none;font-weight:600;font-size:14px}}
</style>
</head>
<body>
<nav><strong style="font-size:18px">OpenShorts</strong><a href="{APP_HOST}/" class="cta">Create Your Video</a></nav>
<h1>AI-Generated UGC Videos</h1>
<p class="subtitle">{len(videos)} videos generated · Low Cost & Premium modes</p>
<div class="grid">{cards_html}</div>
<div style="text-align:center;padding:40px"><a href="{APP_HOST}/" class="cta">Create Your Own UGC Video</a></div>
</body></html>'''


@app.get("/video/{video_id}", response_class=HTMLResponse)
async def video_html_page(video_id: str):
    """SEO individual video page with og:video meta tags."""
    import html as html_mod
    loop = asyncio.get_running_loop()
    videos = await loop.run_in_executor(None, list_video_gallery, 200)
    meta = next((v for v in videos if v.get("video_id") == video_id), None)
    if not meta:
        raise HTTPException(status_code=404, detail="Video not found")

    # Raw values feed the JSON-LD (serialised as JSON by _json_ld) while the
    # escaped ones feed the markup; they are not interchangeable.
    raw_title = meta.get("title", "Untitled")
    raw_caption = meta.get("caption", "")
    title = html_mod.escape(raw_title)
    caption = html_mod.escape(raw_caption)
    narration = html_mod.escape(meta.get("full_narration", ""))
    video_url = meta.get("video_url", "")
    actor_url = meta.get("actor_url", "")
    duration = meta.get("duration", 0)
    mode = meta.get("video_mode", "")
    product = html_mod.escape(meta.get("product_name", ""))
    product_url = html_mod.escape(meta.get("product_url", ""))
    language = meta.get("language", "en")
    hashtags = " ".join(meta.get("hashtags", []))
    cost = meta.get("cost_estimate", {}).get("total", 0)
    created = meta.get("created_at", "")
    actor_desc = html_mod.escape(meta.get("actor_description", ""))

    ld_json = _json_ld(
        {
            "@context": "https://schema.org",
            "@type": "VideoObject",
            "name": raw_title,
            "description": raw_caption,
            "thumbnailUrl": actor_url,
            "contentUrl": video_url,
            "uploadDate": created,
            "duration": f"PT{int(duration)}S",
            "width": 1080,
            "height": 1920,
            "inLanguage": language,
        }
    )

    mode_label = "Low Cost" if mode == "lowcost" else "Premium"

    return f'''<!DOCTYPE html>
<html lang="{language}">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} - AI UGC Video | OpenShorts</title>
<meta name="description" content="{caption} {hashtags}">
<link rel="canonical" href="{GALLERY_HOST}/video/{video_id}">
<meta property="og:type" content="video.other">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{caption}">
<meta property="og:video" content="{video_url}">
<meta property="og:video:type" content="video/mp4">
<meta property="og:video:width" content="1080">
<meta property="og:video:height" content="1920">
<meta property="og:image" content="{actor_url}">
<meta name="twitter:card" content="player">
<meta name="twitter:title" content="{title}">
<meta name="twitter:image" content="{actor_url}">
<script type="application/ld+json">{ld_json}</script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0a0a0c;color:#e4e4e7;font-family:-apple-system,BlinkMacSystemFont,sans-serif}}
nav{{padding:20px 40px;border-bottom:1px solid #27272a;display:flex;align-items:center;gap:16px}}
nav a{{color:#a1a1aa;text-decoration:none;font-size:14px}}
.container{{max-width:1000px;margin:0 auto;padding:40px 20px;display:grid;grid-template-columns:1fr 1fr;gap:40px}}
@media(max-width:768px){{.container{{grid-template-columns:1fr}}}}
video{{width:100%;border-radius:16px;background:#000}}
h1{{font-size:22px;font-weight:700;margin-bottom:8px}}
.meta{{color:#71717a;font-size:13px;margin-bottom:20px}}
.section{{margin-bottom:20px}}
.section h2{{font-size:13px;color:#71717a;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px}}
.section p{{font-size:14px;line-height:1.6}}
.badge{{display:inline-block;padding:3px 10px;border-radius:9999px;font-size:11px;font-weight:700}}
.cta{{display:inline-block;background:#8b5cf6;color:#fff;padding:10px 24px;border-radius:12px;text-decoration:none;font-weight:600;font-size:14px;margin-top:20px}}
</style>
</head>
<body>
<nav><strong>OpenShorts</strong><a href="{GALLERY_HOST}/gallery">Gallery</a><span style="color:#3f3f46">›</span><span style="color:#e4e4e7;font-size:14px">{title}</span></nav>
<div class="container">
<div><video src="{video_url}" poster="{actor_url}" controls autoplay playsinline style="aspect-ratio:9/16;object-fit:cover"></video></div>
<div>
<h1>{title}</h1>
<p class="meta">{duration:.0f}s · {mode_label} · ${cost:.2f} · {product}</p>
<div class="section"><h2>Caption</h2><p>{caption}</p><p style="color:#8b5cf6;margin-top:4px">{hashtags}</p></div>
<div class="section"><h2>Script</h2><p>{narration}</p></div>
<div class="section"><h2>Actor</h2><p>{actor_desc}</p></div>
{f'<div class="section"><h2>Product</h2><p><a href="{product_url}" style="color:#8b5cf6" target="_blank">{product}</a></p></div>' if product_url else ''}
<a href="{GALLERY_HOST}/gallery">← Back to Gallery</a>
<br><a href="{APP_HOST}/" class="cta">Create Your Own</a>
</div>
</div>
</body></html>'''




app.include_router(_mcp_server.router)
from routes.thumbnails import router as thumbnails_router
from routes.clips import router as clips_router
from routes.process import router as process_router
app.include_router(thumbnails_router)
app.include_router(clips_router)
app.include_router(process_router)
