import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Constants
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BACKEND_DIR, "uploads")
OUTPUT_DIR = os.path.join(BACKEND_DIR, "output")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Configuration
MAX_FILE_SIZE_MB = 2048  # 2GB limit

# How TikTok receives our uploads. MEDIA_UPLOAD lands the video in the user's
# TikTok drafts so they finish the post inside TikTok's own editor; DIRECT_POST
# publishes straight to their feed, which is Upload-Post's default.
#
# Drafts are the safer default for an automated pipeline: nothing reaches an
# audience without the account owner seeing it first, and TikTok's own editor is
# where covers, sounds and hashtags actually get chosen. The UI must say so —
# a user who expects a published post and finds a draft will read it as a bug.
TIKTOK_POST_MODE = os.environ.get("TIKTOK_POST_MODE", "MEDIA_UPLOAD").strip()
# Ceiling for the working directory once it lives on a persistent volume: the
# age-based sweep alone can't stop a burst of long videos from filling the disk.
# 0 disables the cap.
OUTPUT_MAX_GB = int(os.environ.get("OUTPUT_MAX_GB", "25"))
# Same idea for source uploads, which are the biggest single files on disk.
UPLOADS_MAX_GB = int(os.environ.get("UPLOADS_MAX_GB", "15"))
# Pre-flight quality gate: warn before processing a YouTube source below this
# height (0 disables). Only applies to URLs; uploads are whatever the user gave.
QUALITY_GATE_MIN_HEIGHT = int(os.environ.get("QUALITY_GATE_MIN_HEIGHT", "720"))
# Reject sources shorter than this before starting (0 disables). A 24s YouTube
# Short cannot yield 15-60s clips: Gemini returns nothing, the job burns
# managed minutes and dies with "no usable clips" (prod 20-ago: 3 of 5 recent
# failures were exactly this, one user retrying the same 24s video).
MIN_SOURCE_SECONDS = int(os.environ.get("MIN_SOURCE_SECONDS", "45"))
QUALITY_PROBE_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "quality_probe.py")
DISABLE_YOUTUBE_URL = os.environ.get("DISABLE_YOUTUBE_URL", "false").lower() in ("1", "true", "yes")

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

# ---- Cloud billing (paid / managed-keys) integration --------------------------
# All paid-mode code lives in the optional `cloud/` package and is imported ONLY
# when BILLING_ENABLED is set. With the flag off, the app behaves exactly as the
# self-hosted BYOK app does today (no extra dependencies required).
BILLING_ENABLED = os.environ.get("BILLING_ENABLED", "").lower() in ("1", "true", "yes")

# Job/file retention (issue #46). Self-host defaults to 24h: the 1h sweep kept
# deleting finished projects under users who never touched their env, and the
# OUTPUT_MAX_GB / UPLOADS_MAX_GB caps below already bound the disk. Cloud keeps
# the tight default because clips are archived to R2 as soon as a job finishes.
JOB_RETENTION_SECONDS = int(
    os.environ.get("JOB_RETENTION_SECONDS", "3600" if BILLING_ENABLED else "86400")
)
# The retained download of a URL job (--keep-original) is the one artifact that
# is a full copy of someone else's video rather than something we made, so it
# can be aged out ahead of the clips it produced. Defaults to the job clock,
# i.e. no change: dropping it earlier costs the clip editor, whose rerender,
# reframe, scenes and EDL endpoints all read that file and answer 409 once it
# is gone. Lower it only if you would rather lose in-session re-edits than
# keep the original around. Uploads are deliberately untouched: that file is
# the user's own content, which they attested to owning.
SOURCE_RETENTION_SECONDS = int(
    os.environ.get("SOURCE_RETENTION_SECONDS", str(JOB_RETENTION_SECONDS))
)
# Force full pipeline logs to the client even under billing (local debugging).
DEBUG_LOGS = os.environ.get("DEBUG_LOGS", "").lower() in ("1", "true", "yes")

THUMBNAILS_DIR = os.path.join(OUTPUT_DIR, 'thumbnails')
os.makedirs(THUMBNAILS_DIR, exist_ok=True)

LAYOUT_ENV = {
    "split": "SPLIT_LAYOUT",          # two speakers stacked
    "screencast": "SCREENCAST_LAYOUT",  # slides/screen share over the speaker
    "speaker_cut": "SPEAKER_CUT",     # hard cuts to whoever is talking
    "punch_in": "PUNCH_IN",           # small push on the clip's beats
}

LAYOUT_IMPLIES = {
    "split": ["SPEAKER_SIGNAL"],
    "speaker_cut": ["SPEAKER_SIGNAL"],
}

UPLOAD_TTL_SECONDS = int(os.environ.get("UPLOAD_TTL_SECONDS", str(6 * 3600)))
SOURCE_URL_TTL_SECONDS = int(os.environ.get("SOURCE_URL_TTL_SECONDS", "21600"))
HEARTBEAT_STALE_AFTER = 60
