import asyncio
import json
import logging
import random
from datetime import datetime, timezone, timedelta
import httpx

from prisma.models import WebhookDelivery, Job

logger = logging.getLogger(__name__)

MAX_RETRIES = 6
MAX_BACKOFF = 3600

_worker_task = None
_stop_event = asyncio.Event()

async def enqueue_webhook(job_id: str, url: str, payload: dict):
    from database.prisma_client import get_prisma
    await get_prisma()
    now = datetime.now(timezone.utc)
    
    await WebhookDelivery.prisma().create(
        data={
            "job_id": job_id,
            "url": url,
            "payload": json.dumps(payload),
            "attempts": 0,
            "status": "pending",
            "next_attempt_at": now,
        }
    )
    logger.info(f"Webhook enqueued for job {job_id} to {url}")

async def webhook_worker():
    logger.info("Starting webhook worker")
    
    while not _stop_event.is_set():
        try:
            await _process_webhooks()
        except Exception as e:
            logger.error(f"Error in webhook worker: {e}")
        
        # Sleep 5 seconds, checking stop event
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pass

    logger.info("Webhook worker stopped")

async def _process_webhooks():
    from database.prisma_client import get_prisma
    await get_prisma()
    now = datetime.now(timezone.utc)
    
    deliveries = await WebhookDelivery.prisma().find_many(
        where={
            "status": {"in": ["pending", "retrying"]},
            "next_attempt_at": {"lte": now}
        },
        take=10
    )

    if not deliveries:
        return

    for delivery in deliveries:
        # Mark as delivering
        delivery = await WebhookDelivery.prisma().update(
            where={"id": delivery.id},
            data={"status": "delivering", "updated_at": datetime.now(timezone.utc)}
        )

        success = False
        last_error = None

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
                headers = {"Content-Type": "application/json", "User-Agent": "OpenShorts-Webhook/1.0"}
                resp = await client.post(delivery.url, content=delivery.payload.encode(), headers=headers)
                if resp.status_code < 300:
                    success = True
                else:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as e:
            last_error = str(e)

        if success:
            await WebhookDelivery.prisma().update(
                where={"id": delivery.id},
                data={
                    "status": "delivered",
                    "updated_at": datetime.now(timezone.utc)
                }
            )
            
            from core.state import jobs
            if delivery.job_id in jobs:
                jobs[delivery.job_id]["webhook_sent"] = True
            
            logger.info(f"Webhook delivered for delivery {delivery.id} (job {delivery.job_id})")
        else:
            attempts = delivery.attempts + 1
            if attempts >= MAX_RETRIES:
                await WebhookDelivery.prisma().update(
                    where={"id": delivery.id},
                    data={
                        "status": "dead_letter",
                        "attempts": attempts,
                        "last_error": last_error,
                        "updated_at": datetime.now(timezone.utc)
                    }
                )
                logger.warning(f"Webhook dead_letter for delivery {delivery.id} (job {delivery.job_id}): {last_error}")
            else:
                base_backoff = 2 ** attempts
                capped_backoff = min(base_backoff, MAX_BACKOFF)
                jitter = capped_backoff * random.uniform(-0.2, 0.2)
                final_backoff = capped_backoff + jitter
                
                next_attempt = datetime.now(timezone.utc) + timedelta(seconds=final_backoff)
                
                await WebhookDelivery.prisma().update(
                    where={"id": delivery.id},
                    data={
                        "status": "retrying",
                        "attempts": attempts,
                        "next_attempt_at": next_attempt,
                        "last_error": last_error,
                        "updated_at": datetime.now(timezone.utc)
                    }
                )
                logger.info(f"Webhook retrying for delivery {delivery.id} (job {delivery.job_id}) in {final_backoff:.1f}s")

def start_webhook_worker():
    global _worker_task
    if _worker_task is None:
        _stop_event.clear()
        _worker_task = asyncio.create_task(webhook_worker())

async def stop_webhook_worker():
    global _worker_task
    if _worker_task is not None:
        _stop_event.set()
        await _worker_task
        _worker_task = None
