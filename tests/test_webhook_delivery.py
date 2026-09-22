import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from backend.services.webhook import enqueue_webhook, _process_webhooks, MAX_RETRIES
from prisma.models import WebhookDelivery, Job
from prisma import Prisma

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
    
    # Clean tables
    await WebhookDelivery.prisma().delete_many()
    await Job.prisma().delete_many()
    
    # Create a job
    await Job.prisma().create(data={"id": "test-job-123"})
    return db

async def _teardown_db(db):
    await WebhookDelivery.prisma().delete_many()
    await Job.prisma().delete_many()
    if db.is_connected():
        await db.disconnect()
    import prisma._registry
    prisma._registry._registered_client = None

def test_webhook_delivery_success_after_retries():
    async def run_test():
        db = await _setup_db()
        try:
            await enqueue_webhook("test-job-123", "http://example.com/webhook", {"event": "test"})
            
            fail_count = 0
            class MockResponse:
                def __init__(self, status_code):
                    self.status_code = status_code
                    self.text = "Mock response"
                    
            async def mock_post(*args, **kwargs):
                nonlocal fail_count
                fail_count += 1
                if fail_count <= 3:
                    return MockResponse(500)
                return MockResponse(200)

            with patch("backend.services.webhook.httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=mock_post):
                # 1st attempt
                await _process_webhooks()
                
                # 2nd attempt
                deliveries = await WebhookDelivery.prisma().find_many()
                d = deliveries[0]
                await WebhookDelivery.prisma().update(where={"id": d.id}, data={"next_attempt_at": datetime.now(timezone.utc)})
                await _process_webhooks()
                
                # 3rd attempt
                d = await WebhookDelivery.prisma().find_first()
                await WebhookDelivery.prisma().update(where={"id": d.id}, data={"next_attempt_at": datetime.now(timezone.utc)})
                await _process_webhooks()
                
                # 4th attempt -> succeeds
                d = await WebhookDelivery.prisma().find_first()
                await WebhookDelivery.prisma().update(where={"id": d.id}, data={"next_attempt_at": datetime.now(timezone.utc)})
                await _process_webhooks()
                
                d = await WebhookDelivery.prisma().find_first()
                assert d.status == "delivered"
                assert fail_count == 4
        finally:
            await _teardown_db(db)

    asyncio.run(run_test())

def test_webhook_delivery_dead_letter():
    async def run_test():
        db = await _setup_db()
        try:
            await enqueue_webhook("test-job-123", "http://example.com/webhook", {"event": "test"})
            
            class MockResponse:
                def __init__(self, status_code):
                    self.status_code = status_code
                    self.text = "Mock response"
                    
            async def mock_post(*args, **kwargs):
                return MockResponse(500)

            with patch("backend.services.webhook.httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=mock_post):
                for _ in range(MAX_RETRIES):
                    await _process_webhooks()
                    d = await WebhookDelivery.prisma().find_first()
                    if d.status == "retrying":
                        await WebhookDelivery.prisma().update(where={"id": d.id}, data={"next_attempt_at": datetime.now(timezone.utc)})
                        
                d = await WebhookDelivery.prisma().find_first()
                assert d.status == "dead_letter"
                assert d.attempts == MAX_RETRIES
        finally:
            await _teardown_db(db)

    asyncio.run(run_test())

