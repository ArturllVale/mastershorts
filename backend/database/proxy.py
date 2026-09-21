import asyncio
import json
from .prisma_client import get_prisma
from typing import Dict, Any, List

def run_async(coro):
    """Run an async coroutine synchronously using the current or new event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # If we're already in an event loop (e.g. FastAPI request), we can't block with run_until_complete easily.
        # But for magic methods, we need to return synchronously.
        # We will use a background thread or a nested event loop if needed, but standard library asyncio
        # doesn't allow run_until_complete on a running loop.
        # As a hack for sync methods in an async context (since Prisma is strictly async),
        # we can use nest_asyncio if available or run in a new thread.
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(coro)
    else:
        return asyncio.run(coro)

# Internal helper functions for Prisma
async def _get_job(job_id: str) -> Dict[str, Any]:
    prisma = await get_prisma()
    job = await prisma.job.find_unique(where={"id": job_id}, include={"logs": True})
    if job:
        # Convert to dict
        data = job.model_dump()
        # Parse JSON strings
        for json_field in ["cmd", "env", "ready_files", "result", "partial", "attestation"]:
            if data.get(json_field):
                try:
                    data[json_field] = json.loads(data[json_field])
                except Exception:
                    data[json_field] = {} if json_field in ["env", "ready_files"] else []

        # Parse logs
        data["logs"] = [log["message"] for log in data.get("logs", [])]

        # Datetime to string
        if data.get("created_at"):
            data["created_at"] = data["created_at"].isoformat()

        return data
    return {}

async def _create_or_update_job(job_id: str, data: Dict[str, Any]):
    prisma = await get_prisma()

    # Pre-process data
    update_data = {}
    for k, v in data.items():
        if k in ["cmd", "env", "ready_files", "result", "partial", "attestation"]:
            update_data[k] = json.dumps(v)
        elif k != "logs" and k != "id" and k != "created_at":
            update_data[k] = v

    # Check if exists
    job = await prisma.job.find_unique(where={"id": job_id})
    if not job:
        # Create
        create_data = dict(update_data)
        create_data["id"] = job_id
        await prisma.job.create(data=create_data)
    else:
        # Update
        if update_data:
            await prisma.job.update(where={"id": job_id}, data=update_data)

async def _update_job_field(job_id: str, field: str, value: Any):
    prisma = await get_prisma()

    if field in ["cmd", "env", "ready_files", "result", "partial", "attestation"]:
        val = json.dumps(value)
    else:
        val = value

    await prisma.job.update(where={"id": job_id}, data={field: val})

async def _update_job_dict_field(job_id: str, field: str, subkey: Any, subvalue: Any):
    prisma = await get_prisma()
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
    prisma = await get_prisma()
    await prisma.joblog.create(data={"job_id": job_id, "message": log})

async def _delete_job(job_id: str):
    prisma = await get_prisma()
    await prisma.job.delete(where={"id": job_id})

async def _get_all_jobs() -> List[Dict[str, Any]]:
    prisma = await get_prisma()
    jobs = await prisma.job.find_many(include={"logs": True})
    result = []
    for job in jobs:
        data = job.model_dump()
        # Parse JSON strings
        for json_field in ["cmd", "env", "ready_files", "result", "partial", "attestation"]:
            if data.get(json_field):
                try:
                    data[json_field] = json.loads(data[json_field])
                except Exception:
                    data[json_field] = {} if json_field in ["env", "ready_files"] else []

        # Parse logs
        data["logs"] = [log["message"] for log in data.get("logs", [])]

        if data.get("created_at"):
            data["created_at"] = data["created_at"].isoformat()
        result.append(data)
    return result

async def _job_exists(job_id: str) -> bool:
    prisma = await get_prisma()
    job = await prisma.job.find_unique(where={"id": job_id})
    return job is not None


class DBJobsProxy:
    def __contains__(self, key):
        return run_async(_job_exists(key))
        
    def __getitem__(self, key):
        if not run_async(_job_exists(key)):
            raise KeyError(key)
        # return a proxy dictionary that captures modifications
        return JobDictProxy(key, run_async(_get_job(key)))
        
    def __setitem__(self, key, value):
        run_async(_create_or_update_job(key, value))
        
    def __delitem__(self, key):
        run_async(_delete_job(key))
        
    def get(self, key, default=None):
        if run_async(_job_exists(key)):
            return self[key]
        return default
        
    def pop(self, key, default=None):
        if run_async(_job_exists(key)):
            val = run_async(_get_job(key))
            run_async(_delete_job(key))
            return val
        return default

    def values(self):
        return run_async(_get_all_jobs())
        
    def keys(self):
        return [j['id'] for j in run_async(_get_all_jobs())]
        
    def items(self):
        return [(j['id'], j) for j in run_async(_get_all_jobs())]

class JobDictProxy(dict):
    def __init__(self, job_id, data):
        super().__init__(data)
        self.job_id = job_id
        
    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        run_async(_update_job_field(self.job_id, key, value))
        
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
        run_async(_append_job_log(self.job_id, val))

class SubDictProxy(dict):
    def __init__(self, job_id, field, data):
        super().__init__(data)
        self.job_id = job_id
        self.field = field
        
    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        run_async(_update_job_dict_field(self.job_id, self.field, key, value))
        
    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]
