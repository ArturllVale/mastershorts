import asyncio
import json
import os
import threading
import concurrent.futures
from typing import Dict, Any, List

try:
    from prisma import Prisma
    HAS_PRISMA = True
except (ImportError, ModuleNotFoundError, AttributeError):
    Prisma = None
    HAS_PRISMA = False

from .operations import (
    get_job as _sqla_get_job,
    create_or_update_job as _sqla_create_or_update_job,
    update_job_status as _sqla_update_job_status,
    append_job_log as _sqla_append_job_log,
    update_job_field as _sqla_update_job_field,
    update_job_dict_field as _sqla_update_job_dict_field,
    delete_job as _sqla_delete_job,
    get_all_jobs as _sqla_get_all_jobs,
    job_exists as _sqla_job_exists,
)

# We manage our own isolated Prisma client instance strictly for the background event loop
# to ensure thread safety and avoid bleeding connections across different async runtimes
_bg_prisma = None
_bg_loop = None

def _get_bg_loop():
    global _bg_loop
    if _bg_loop is None:
        _bg_loop = asyncio.new_event_loop()
        t = threading.Thread(target=_bg_loop.run_forever, daemon=True)
        t.start()
    return _bg_loop

async def _ensure_tables(prisma):
    try:
        await prisma.job.count()
    except Exception:
        ddl = [
            """CREATE TABLE IF NOT EXISTS "Job" (
                "id" TEXT NOT NULL PRIMARY KEY,
                "status" TEXT NOT NULL DEFAULT 'queued',
                "source_hash" TEXT,
                "config_hash" TEXT,
                "cmd" TEXT,
                "env" TEXT,
                "output_dir" TEXT,
                "attestation" TEXT,
                "user_id" TEXT,
                "reservation_id" TEXT,
                "watermark" BOOLEAN NOT NULL DEFAULT false,
                "partial" TEXT,
                "webhook_url" TEXT,
                "webhook_secret" TEXT,
                "base_url" TEXT,
                "proxy_bytes" INTEGER,
                "proxy_route" TEXT,
                "ready_files" TEXT,
                "result" TEXT,
                "error" TEXT,
                "created_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            );""",
            """CREATE TABLE IF NOT EXISTS "JobLog" (
                "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                "job_id" TEXT NOT NULL,
                "message" TEXT NOT NULL,
                "created_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT "JobLog_job_id_fkey" FOREIGN KEY ("job_id") REFERENCES "Job" ("id") ON DELETE CASCADE ON UPDATE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS "Clip" (
                "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                "job_id" TEXT NOT NULL,
                "title" TEXT,
                CONSTRAINT "Clip_job_id_fkey" FOREIGN KEY ("job_id") REFERENCES "Job" ("id") ON DELETE CASCADE ON UPDATE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS "ClipAsset" (
                "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                "clip_id" INTEGER NOT NULL,
                "file_path" TEXT NOT NULL,
                CONSTRAINT "ClipAsset_clip_id_fkey" FOREIGN KEY ("clip_id") REFERENCES "Clip" ("id") ON DELETE CASCADE ON UPDATE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS "WebhookDelivery" (
                "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                "job_id" TEXT NOT NULL,
                "status_code" INTEGER NOT NULL,
                "response_body" TEXT,
                CONSTRAINT "WebhookDelivery_job_id_fkey" FOREIGN KEY ("job_id") REFERENCES "Job" ("id") ON DELETE CASCADE ON UPDATE CASCADE
            );"""
        ]
        for stmt in ddl:
            try:
                await prisma.execute_raw(stmt)
            except Exception:
                pass

    # Ensure backward-compatible migrations on existing sqlite databases
    for col_stmt in [
        'ALTER TABLE "Job" ADD COLUMN "source_hash" TEXT;',
        'ALTER TABLE "Job" ADD COLUMN "config_hash" TEXT;',
    ]:
        try:
            await prisma.execute_raw(col_stmt)
        except Exception:
            pass

async def _get_bg_prisma():
    global _bg_prisma
    if not os.environ.get("DATABASE_URL"):
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dev.db")).replace("\\", "/")
        os.environ["DATABASE_URL"] = f"file:{db_path}"
    if _bg_prisma is None:
        _bg_prisma = Prisma(auto_register=False)
        await _bg_prisma.connect()
        await _ensure_tables(_bg_prisma)
    elif not _bg_prisma.is_connected():
        await _bg_prisma.connect()
        await _ensure_tables(_bg_prisma)
    return _bg_prisma

def run_async(coro):
    """Run an async coroutine synchronously using a dedicated background event loop.
    This prevents 'Event loop is closed' errors when running async code inside
    synchronous contexts without corrupting any globally running event loops."""
    future = asyncio.run_coroutine_threadsafe(coro, _get_bg_loop())
    return future.result()

# Internal helper functions for Prisma
async def _get_job(job_id: str) -> Dict[str, Any]:
    prisma = await _get_bg_prisma()
    job = await prisma.job.find_unique(where={"id": job_id}, include={"logs": True})
    if job:
        data = job.model_dump()
        for json_field in ["cmd", "env", "ready_files", "result", "partial", "attestation"]:
            if data.get(json_field):
                try:
                    data[json_field] = json.loads(data[json_field])
                    if json_field == "ready_files" and isinstance(data[json_field], dict):
                         data[json_field] = {int(k) if str(k).isdigit() else k: v for k, v in data[json_field].items()}
                except Exception:
                    data[json_field] = {} if json_field in ["env", "ready_files"] else []
            elif json_field in ["env", "ready_files"]:
                data[json_field] = {}
            elif json_field in ["cmd"]:
                data[json_field] = []
        data["logs"] = [log["message"] for log in data.get("logs", [])]
        if data.get("created_at"):
            data["created_at"] = data["created_at"].isoformat()
        return data
    return {}

VALID_JOB_FIELDS = {
    "status", "cmd", "env", "output_dir", "attestation",
    "user_id", "reservation_id", "watermark", "partial",
    "webhook_url", "webhook_secret", "base_url", "proxy_bytes",
    "proxy_route", "ready_files", "result", "error",
    "source_hash", "config_hash"
}

async def _create_or_update_job(job_id: str, data: Dict[str, Any]):
    prisma = await _get_bg_prisma()
    update_data = {}
    for k, v in data.items():
        if k not in VALID_JOB_FIELDS:
            continue
        if k in ["cmd", "env", "ready_files", "result", "partial", "attestation"]:
            update_data[k] = json.dumps(v)
        else:
            update_data[k] = v

    job = await prisma.job.find_unique(where={"id": job_id})
    if not job:
        create_data = dict(update_data)
        create_data["id"] = job_id
        await prisma.job.create(data=create_data)
    else:
        if update_data:
            await prisma.job.update(where={"id": job_id}, data=update_data)

async def _update_job_field(job_id: str, field: str, value: Any):
    if field not in VALID_JOB_FIELDS:
        return
    prisma = await _get_bg_prisma()
    if field in ["cmd", "env", "ready_files", "result", "partial", "attestation"]:
        val = json.dumps(value)
    else:
        val = value
    await prisma.job.update(where={"id": job_id}, data={field: val})

async def _update_job_dict_field(job_id: str, field: str, subkey: Any, subvalue: Any):
    prisma = await _get_bg_prisma()
    job = await prisma.job.find_unique(where={"id": job_id})
    if job:
        current = getattr(job, field)
        try:
            current_dict = json.loads(current) if current else {}
        except Exception:
            current_dict = {}
        current_dict[str(subkey)] = subvalue
        await prisma.job.update(where={"id": job_id}, data={field: json.dumps(current_dict)})

async def _append_job_log(job_id: str, log: str):
    prisma = await _get_bg_prisma()
    await prisma.joblog.create(data={"job_id": job_id, "message": log})

async def _delete_job(job_id: str):
    prisma = await _get_bg_prisma()
    await prisma.job.delete(where={"id": job_id})

async def _get_all_jobs() -> List[Dict[str, Any]]:
    prisma = await _get_bg_prisma()
    jobs = await prisma.job.find_many(include={"logs": True})
    result = []
    for job in jobs:
        data = job.model_dump()
        for json_field in ["cmd", "env", "ready_files", "result", "partial", "attestation"]:
            if data.get(json_field):
                try:
                    data[json_field] = json.loads(data[json_field])
                    if json_field == "ready_files" and isinstance(data[json_field], dict):
                         data[json_field] = {int(k) if str(k).isdigit() else k: v for k, v in data[json_field].items()}
                except Exception:
                    data[json_field] = {} if json_field in ["env", "ready_files"] else []
            elif json_field in ["env", "ready_files"]:
                data[json_field] = {}
            elif json_field in ["cmd"]:
                data[json_field] = []
        data["logs"] = [log["message"] for log in data.get("logs", [])]
        if data.get("created_at"):
            data["created_at"] = data["created_at"].isoformat()
        result.append(data)
    return result

async def _job_exists(job_id: str) -> bool:
    prisma = await _get_bg_prisma()
    job = await prisma.job.find_unique(where={"id": job_id})
    return job is not None


class DBJobsProxy:
    def __contains__(self, key):
        if HAS_PRISMA:
            return run_async(_job_exists(key))
        return _sqla_job_exists(key)
        
    def __getitem__(self, key):
        if HAS_PRISMA:
            if not run_async(_job_exists(key)):
                raise KeyError(key)
            return JobDictProxy(key, run_async(_get_job(key)))
        if not _sqla_job_exists(key):
            raise KeyError(key)
        return JobDictProxy(key, _sqla_get_job(key))
        
    def __setitem__(self, key, value):
        if HAS_PRISMA:
            run_async(_create_or_update_job(key, value))
        else:
            _sqla_create_or_update_job(key, value)
        
    def __delitem__(self, key):
        if HAS_PRISMA:
            run_async(_delete_job(key))
        else:
            _sqla_delete_job(key)
        
    def get(self, key, default=None):
        if key in self:
            return self[key]
        return default
        
    def pop(self, key, default=None):
        if key in self:
            val = self[key]
            del self[key]
            return val
        return default

    def values(self):
        if HAS_PRISMA:
            return run_async(_get_all_jobs())
        return _sqla_get_all_jobs()
        
    def keys(self):
        if HAS_PRISMA:
            return [j['id'] for j in run_async(_get_all_jobs())]
        return [j['id'] for j in _sqla_get_all_jobs()]
        
    def items(self):
        if HAS_PRISMA:
            return [(j['id'], j) for j in run_async(_get_all_jobs())]
        return [(j['id'], j) for j in _sqla_get_all_jobs()]

class JobDictProxy(dict):
    def __init__(self, job_id, data):
        super().__init__(data)
        self.job_id = job_id
        
    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        if HAS_PRISMA:
            run_async(_update_job_field(self.job_id, key, value))
        else:
            _sqla_update_job_field(self.job_id, key, value)
        
    def __getitem__(self, key):
        val = super().__getitem__(key)
        if isinstance(val, list):
            if key == 'logs':
                return LogListProxy(self.job_id, val)
        if isinstance(val, dict):
            return SubDictProxy(self.job_id, key, val)
        return val

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]

class LogListProxy(list):
    def __init__(self, job_id, data):
        super().__init__(data)
        self.job_id = job_id
        
    def append(self, val):
        super().append(val)
        if HAS_PRISMA:
            run_async(_append_job_log(self.job_id, val))
        else:
            _sqla_append_job_log(self.job_id, val)

class SubDictProxy(dict):
    def __init__(self, job_id, field, data):
        super().__init__(data)
        self.job_id = job_id
        self.field = field
        
    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        if HAS_PRISMA:
            run_async(_update_job_dict_field(self.job_id, self.field, key, value))
        else:
            _sqla_update_job_dict_field(self.job_id, self.field, key, value)
        
    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]
