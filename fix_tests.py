import os
import glob
import re

for filepath in glob.glob("tests/*.py"):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # If it imports app_module, let's also import core.state and services.job_queue and routes.process
    if "pytest.importorskip(\"app\")" in content or "import app as app_module" in content:
        if "from core import state" not in content:
            content = content.replace("app_module = pytest.importorskip(\"app\")", "app_module = pytest.importorskip(\"app\")\n    from core import state\n    from services import job_queue\n    from routes import process")
            content = content.replace("import app as app_module", "import app as app_module\nfrom core import state\nfrom services import job_queue\nfrom routes import process")

    replacements = [
        ('monkeypatch.setattr(app_module, "jobs"', 'monkeypatch.setattr(state, "jobs"'),
        ('monkeypatch.setattr(app_module, "job_queue"', 'monkeypatch.setattr(state, "job_queue"'),
        ('monkeypatch.setattr(app_module, "pending_uploads"', 'monkeypatch.setattr(state, "pending_uploads"'),
        ('monkeypatch.setattr(app_module, "_probe_youtube_quality"', 'monkeypatch.setattr(process, "_probe_youtube_quality"'),
        ('monkeypatch.setattr(app_module, "_media_duration_seconds"', 'monkeypatch.setattr(process, "_media_duration_seconds"'),
        ('monkeypatch.setattr(app_module, "OUTPUT_DIR"', 'monkeypatch.setattr("core.config.OUTPUT_DIR"'),
        ('monkeypatch.setattr(app_module, "UPLOAD_DIR"', 'monkeypatch.setattr("core.config.UPLOAD_DIR"'),
        ('monkeypatch.setattr(app_module.job_queue', 'monkeypatch.setattr(state.job_queue'),
        ('app_module.jobs', 'state.jobs'),
        ('app_module.job_queue', 'state.job_queue'),
        ('app_module.pending_uploads', 'state.pending_uploads'),
        ('app_module._probe_youtube_quality', 'process._probe_youtube_quality'),
        ('app_module._media_duration_seconds', 'process._media_duration_seconds'),
        ('app_module._sweep_pending_uploads', 'job_queue._sweep_pending_uploads'),
        ('app_module.UPLOAD_TTL_SECONDS', '14400'), # Hardcode for now
        ('app_module._touch_manifest', 'job_queue._touch_manifest'),
        ('app_module._read_manifest', 'job_queue._read_manifest'),
        ('app_module._manifest_busy_elsewhere', 'job_queue._manifest_busy_elsewhere'),
        ('app_module._resume_interrupted_jobs', 'job_queue._resume_interrupted_jobs'),
        ('app_module._RESUME_FILE', 'job_queue._RESUME_FILE'),
        ('app_module.HEARTBEAT_STALE_AFTER', '300'),
        ('app_module.MAX_RESUME_ATTEMPTS', '3'),
        ('app_module._job_error_text', 'job_queue._job_error_text'),
        ('app_module.thumbnail_sessions', 'state.thumbnail_sessions')
    ]

    for old, new in replacements:
        content = content.replace(old, new)
        
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
print("Done patching tests.")
