import os
import sys

# Make the repo root and backend importable so tests can import the app modules directly.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Tests always run the app in self-host (BYOK) mode. app.py freezes
# BILLING_ENABLED at import time and load_dotenv never overrides an existing
# variable, so this must be set here — before any test module imports app — or
# the suite's behavior would depend on the developer's personal .env.
os.environ["BILLING_ENABLED"] = "0"

import pytest

@pytest.fixture(autouse=True)
def _sync_app_monkeypatch(monkeypatch):
    orig_setattr = monkeypatch.setattr

    def patched_setattr(*args, **kwargs):
        orig_setattr(*args, **kwargs)
        if len(args) < 3:
            return
        target, name, value = args[0], args[1], args[2]
        target_name = getattr(target, "__name__", "")
        if target_name == "app":
            if name in (
                "OUTPUT_DIR", "UPLOAD_DIR", "THUMBNAILS_DIR", "MIN_SOURCE_SECONDS",
                "QUALITY_GATE_MIN_HEIGHT", "BILLING_ENABLED",
                "SOURCE_RETENTION_SECONDS", "JOB_RETENTION_SECONDS"
            ):
                if "core.config" in sys.modules:
                    orig_setattr(sys.modules["core.config"], name, value)
                for mod_name in ("services.job_queue", "routes.process", "routes.clips", "routes.thumbnails"):
                    if mod_name in sys.modules and hasattr(sys.modules[mod_name], name):
                        orig_setattr(sys.modules[mod_name], name, value)

            if name in (
                "jobs", "pending_uploads", "thumbnail_sessions", "publish_jobs",
                "concurrency_semaphore", "job_queue"
            ):
                if "core.state" in sys.modules:
                    orig_setattr(sys.modules["core.state"], name, value)
                for mod_name in ("services.job_queue", "routes.process", "routes.clips", "routes.thumbnails"):
                    if mod_name in sys.modules and hasattr(sys.modules[mod_name], name):
                        orig_setattr(sys.modules[mod_name], name, value)

            if name in (
                "_probe_youtube_quality", "_media_duration_seconds",
                "_signed_source_url", "_source_signature", "_presented_status"
            ):
                for mod_name in ("routes.process", "routes.clips", "services.job_queue"):
                    if mod_name in sys.modules and hasattr(sys.modules[mod_name], name):
                        orig_setattr(sys.modules[mod_name], name, value)

            if name in (
                "INSTANCE_ID", "_draining", "_stopping", "_running_jobs",
                "_touch_manifest", "_read_manifest", "_manifest_busy_elsewhere",
                "_sweep_retained_sources", "_sweep_pending_uploads"
            ):
                if "services.job_queue" in sys.modules and hasattr(sys.modules["services.job_queue"], name):
                    orig_setattr(sys.modules["services.job_queue"], name, value)

    monkeypatch.setattr = patched_setattr
