from sqlalchemy.orm.attributes import flag_modified
from .connection import SessionLocal
from .models import Job
from typing import Dict, Any, List

def get_job(job_id: str) -> Dict[str, Any]:
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            return job.to_dict()
        return {}

def create_or_update_job(job_id: str, data: Dict[str, Any]):
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            job = Job(id=job_id)
            db.add(job)
        for k, v in data.items():
            if hasattr(job, k):
                setattr(job, k, v)
        db.commit()

def update_job_status(job_id: str, status: str):
    with SessionLocal() as db:
        db.query(Job).filter(Job.id == job_id).update({"status": status})
        db.commit()

def append_job_log(job_id: str, log: str):
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            if job.logs is None:
                job.logs = []
            job.logs = job.logs + [log]
            flag_modified(job, "logs")
            db.commit()

def update_job_field(job_id: str, field: str, value: Any):
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            setattr(job, field, value)
            flag_modified(job, field)
            db.commit()

def update_job_dict_field(job_id: str, field: str, subkey: Any, subvalue: Any):
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            d = getattr(job, field)
            if not d:
                d = {}
            # Need a copy to ensure SQLAlchemy detects change
            new_d = dict(d)
            new_d[str(subkey)] = subvalue
            setattr(job, field, new_d)
            flag_modified(job, field)
            db.commit()

def delete_job(job_id: str):
    with SessionLocal() as db:
        db.query(Job).filter(Job.id == job_id).delete()
        db.commit()

def get_all_jobs() -> List[Dict[str, Any]]:
    with SessionLocal() as db:
        return [j.to_dict() for j in db.query(Job).all()]

def job_exists(job_id: str) -> bool:
    with SessionLocal() as db:
        return db.query(Job).filter(Job.id == job_id).first() is not None
