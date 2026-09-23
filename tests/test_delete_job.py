import os
import pytest
from fastapi.testclient import TestClient
import app as app_module
from services.job_queue import delete_single_job, jobs, _running_jobs

client = TestClient(app_module.app)

def test_delete_single_job(tmp_path, monkeypatch):
    import services.job_queue as jq
    monkeypatch.setattr(jq, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(jq, "UPLOAD_DIR", str(tmp_path / "uploads"))
    
    out_dir = tmp_path / "output" / "job-123"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "clip_1.mp4").write_text("dummy")

    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    (uploads_dir / "job-123_video.mp4").write_text("dummy_upload")

    jobs["job-123"] = {
        "status": "completed",
        "output_dir": str(out_dir),
    }
    _running_jobs.add("job-123")

    assert delete_single_job("job-123") is True
    assert not out_dir.exists()
    assert not (uploads_dir / "job-123_video.mp4").exists()
    assert "job-123" not in jobs
    assert "job-123" not in _running_jobs

def test_delete_job_api_endpoint(tmp_path, monkeypatch):
    import services.job_queue as jq
    monkeypatch.setattr(jq, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(jq, "UPLOAD_DIR", str(tmp_path / "uploads"))

    job_id = "job-to-delete-api"
    jobs[job_id] = {"status": "completed"}

    res = client.delete(f"/api/jobs/{job_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["job_id"] == job_id
    assert job_id not in jobs
