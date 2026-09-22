import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

import app as app_module
from services.idempotency import compute_source_hash, compute_config_hash
from prisma.models import Job
from prisma import Prisma

client = TestClient(app_module.app)

async def _setup_db():
    db = Prisma()
    import prisma
    from prisma.errors import ClientNotRegisteredError
    try:
        db = prisma.get_client()
    except ClientNotRegisteredError:
        db = Prisma()
        prisma.register(db)
    
    if not db.is_connected():
        await db.connect()
    
    await Job.prisma().delete_many()
    return db

async def _teardown_db(db):
    await Job.prisma().delete_many()
    if db.is_connected():
        await db.disconnect()
    import prisma._registry
    prisma._registry._registered_client = None

def test_idempotency_same_post():
    async def run_test():
        db = await _setup_db()
        try:
            from httpx import AsyncClient, ASGITransport
            transport = ASGITransport(app=app_module.app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                url = "http://example.com/video"
                
                with patch("routes.process._probe_youtube_quality", new_callable=AsyncMock, return_value={"duration": 100, "max_height": 720}), \
                     patch("routes.process.reserve_process_minutes", new_callable=AsyncMock, return_value=("user-1", 1, "res-1", "free", None)), \
                     patch("routes.process._enqueue_job"):
                    
                    response1 = await client.post(
                        "/api/process",
                        json={"url": url, "acknowledged": "true"},
                        headers={"X-LLM-Base-URL": "http://localhost", "X-LLM-Model": "test", "Content-Type": "application/x-www-form-urlencoded"},
                        data={"url": url, "acknowledged": "true"}
                    )
                    assert response1.status_code == 200
                    job1_id = response1.json()["job_id"]
                    
                    # Need to wait a little for the DB proxy to save the job
                    await asyncio.sleep(0.5)

                    response2 = await client.post(
                        "/api/process",
                        json={"url": url, "acknowledged": "true"},
                        headers={"X-LLM-Base-URL": "http://localhost", "X-LLM-Model": "test", "Content-Type": "application/x-www-form-urlencoded"},
                        data={"url": url, "acknowledged": "true"}
                    )

                    assert response2.status_code == 200
                    data = response2.json()
                    assert data["job_id"] == job1_id
                    assert response2.headers.get("X-Idempotent") == "true"
                    
                    jobs = await Job.prisma().find_many()
                    assert len(jobs) == 1
        finally:
            await _teardown_db(db)
    asyncio.run(run_test())

def test_idempotency_different_prompts():
    async def run_test():
        db = await _setup_db()
        try:
            from httpx import AsyncClient, ASGITransport
            transport = ASGITransport(app=app_module.app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                url = "http://example.com/video"
                
                with patch("routes.process._probe_youtube_quality", new_callable=AsyncMock, return_value={"duration": 100, "max_height": 720}), \
                     patch("routes.process.reserve_process_minutes", new_callable=AsyncMock, return_value=("user-1", 1, "res-1", "free", None)), \
                     patch("routes.process._enqueue_job"):
                    
                    response1 = await client.post(
                        "/api/process",
                        data={"url": url, "acknowledged": "true", "target_clips": "3"},
                        headers={"X-LLM-Base-URL": "http://localhost", "X-LLM-Model": "test", "Content-Type": "application/x-www-form-urlencoded"}
                    )
                    assert response1.status_code == 200
                    job1_id = response1.json()["job_id"]
                    assert response1.headers.get("X-Idempotent") is None

                    # Let proxy save it
                    await asyncio.sleep(0.5)

                    response2 = await client.post(
                        "/api/process",
                        data={"url": url, "acknowledged": "true", "target_clips": "5"},
                        headers={"X-LLM-Base-URL": "http://localhost", "X-LLM-Model": "test", "Content-Type": "application/x-www-form-urlencoded"}
                    )
                    assert response2.status_code == 200
                    job2_id = response2.json()["job_id"]
                    assert response2.headers.get("X-Idempotent") is None
                    assert job1_id != job2_id
                    
        finally:
            await _teardown_db(db)
    asyncio.run(run_test())
