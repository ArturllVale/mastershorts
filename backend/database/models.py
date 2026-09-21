from sqlalchemy import Column, String, Integer, Boolean, JSON, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
import datetime

Base = declarative_base()

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(String, primary_key=True, index=True)
    status = Column(String, default="queued")
    logs = Column(JSON, default=list)
    cmd = Column(JSON, default=list)
    env = Column(JSON, default=dict)
    output_dir = Column(String, nullable=True)
    attestation = Column(JSON, nullable=True)
    user_id = Column(String, nullable=True)
    reservation_id = Column(String, nullable=True)
    watermark = Column(Boolean, default=False)
    partial = Column(JSON, nullable=True)
    webhook_url = Column(String, nullable=True)
    webhook_secret = Column(String, nullable=True)
    base_url = Column(String, nullable=True)
    
    proxy_bytes = Column(Integer, nullable=True)
    proxy_route = Column(String, nullable=True)
    
    ready_files = Column(JSON, default=dict)
    result = Column(JSON, nullable=True)
    error = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'status': self.status,
            'logs': self.logs or [],
            'cmd': self.cmd or [],
            'env': self.env or {},
            'output_dir': self.output_dir,
            'attestation': self.attestation,
            'user_id': self.user_id,
            'reservation_id': self.reservation_id,
            'watermark': self.watermark,
            'partial': self.partial,
            'webhook_url': self.webhook_url,
            'webhook_secret': self.webhook_secret,
            'base_url': self.base_url,
            'proxy_bytes': self.proxy_bytes,
            'proxy_route': self.proxy_route,
            'ready_files': {int(k) if isinstance(k, str) and k.isdigit() else k: v for k, v in (self.ready_files or {}).items()},
            'result': self.result,
            'error': self.error,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
