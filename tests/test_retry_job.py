import os
import json
import pytest
from services.job_queue import save_job_spec, load_job_spec, retry_job, jobs, _running_jobs
from core.state import job_queue

def test_save_and_load_job_spec(tmp_path, monkeypatch):
    import services.job_queue as jq
    monkeypatch.setattr(jq, "OUTPUT_DIR", str(tmp_path))

    job_id = "test-job-spec-1"
    job_data = {
        "cmd": ["python", "main.py", "-u", "https://youtube.com/watch?v=123"],
        "priority": 1,
        "user_id": "user-42",
        "reservation_id": "res-99",
        "watermark": True,
        "partial": None,
        "output_dir": str(tmp_path / job_id),
        "env": {"LLM_PROVIDER": "openai", "LLM_BASE_URL": "http://localhost:8000/v1"}
    }
    save_job_spec(job_id, job_data)

    loaded = load_job_spec(job_id)
    assert loaded is not None
    assert loaded["cmd"] == job_data["cmd"]
    assert loaded["user_id"] == "user-42"
    assert loaded["env_overrides"]["LLM_BASE_URL"] == "http://localhost:8000/v1"

def test_retry_failed_job(tmp_path, monkeypatch):
    import services.job_queue as jq
    monkeypatch.setattr(jq, "OUTPUT_DIR", str(tmp_path))

    job_id = "test-job-retry-2"
    job_dir = tmp_path / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    jobs[job_id] = {
        "status": "failed",
        "logs": ["Process started", "❌ Gemini Error: [WinError 10061] Connection refused"],
        "cmd": ["python", "main.py", "-o", str(job_dir)],
        "env": {"LLM_BASE_URL": "http://localhost:8000/v1"},
        "output_dir": str(job_dir),
        "result": None,
        "priority": 0,
    }

    retried = retry_job(job_id, overrides={"llm_base_url": "http://localhost:9000/v1"})
    assert retried["status"] == "queued"
    assert retried["env"]["LLM_BASE_URL"] == "http://localhost:9000/v1"
    assert any("Retomando processamento" in l for l in retried["logs"])
    assert job_id in [j[2] for j in list(job_queue._queue)]
