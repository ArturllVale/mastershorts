import asyncio
import itertools
import os
from typing import Dict

# Default to 1 if not set, but user can set higher for powerful servers
MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", "5"))

# Application State
# PriorityQueue holds (priority, seq, job_id). Lower priority dispatches first:
# pro=0, starter/creator=1, BYOK/anonymous/self-host=2. The seq counter keeps
# FIFO order within a priority and makes the tuples always comparable. With
# BILLING disabled every job enqueues at priority 2 → plain FIFO as before.
job_queue = asyncio.PriorityQueue()
_job_seq = itertools.count()
from database.proxy import DBJobsProxy
jobs = DBJobsProxy()
thumbnail_sessions: Dict[str, Dict] = {}
# Semaphore to limit concurrency to MAX_CONCURRENT_JOBS
concurrency_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

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

publish_jobs = {}

_running_jobs = set()
_restore_locks: Dict[str, asyncio.Lock] = {}


def _enqueue_job(job_id: str, priority: int = 2):
    job_queue.put_nowait((priority, next(_job_seq), job_id))
