import hashlib
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from prisma.models import Job

# Se existir job completed com mesmo par nas últimas 24h, retorne o existente.
COMPLETED_JOB_MAX_AGE_HOURS = 24

def _normalize_url(url: str) -> str:
    return url.strip().split("#")[0]

async def compute_source_hash(
    url: Optional[str] = None, 
    file_path: Optional[str] = None
) -> str:
    """
    source_hash = SHA256 do arquivo se upload; URL canônica normalizada
    se link. Se link e conteúdo não verificável, use a URL como base e
    registre "não verificável" no hash para não bloquear.
    """
    if url:
        normalized = _normalize_url(url)
        return hashlib.sha256(f"url_unverifiable:{normalized}".encode()).hexdigest()
    
    if file_path and os.path.exists(file_path):
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192 * 4):
                sha256.update(chunk)
        return sha256.hexdigest()

    return hashlib.sha256(b"unknown_source").hexdigest()

def compute_config_hash(config: Dict[str, Any]) -> str:
    """
    config_hash = SHA256 do JSON canônico. Ordene chaves antes de hashear.
    """
    canonical = json.dumps(config, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()

async def find_idempotent_job(source_hash: str, config_hash: str) -> Optional[Job]:
    """
    Verifica se já existe um Job com o mesmo source_hash e config_hash.
    Se estiver queued ou processing, retorna o job existente.
    Se estiver completed nas últimas 24h, retorna o existente.
    Caso contrário (falhou ou muito antigo), permite criar novo.
    """
    jobs = await Job.prisma().find_many(
        where={
            "source_hash": source_hash,
            "config_hash": config_hash
        },
        order={"created_at": "desc"}
    )
    
    for job in jobs:
        if job.status in ["queued", "processing"]:
            return job
            
        if job.status == "completed":
            age = datetime.now(timezone.utc) - job.created_at
            if age.total_seconds() <= COMPLETED_JOB_MAX_AGE_HOURS * 3600:
                return job
                
    return None
