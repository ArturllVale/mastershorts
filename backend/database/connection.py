import warnings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base
from .prisma_client import get_prisma, disconnect_prisma

# Deprecated SQLAlchemy connection
DATABASE_URL = "sqlite:///./jobs.db"

# check_same_thread=False is needed for FastAPI+SQLite
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

def get_db():
    warnings.warn("get_db is deprecated. Use Prisma instead.", DeprecationWarning)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Expose Prisma functions directly for convenience
__all__ = ["get_db", "SessionLocal", "engine", "get_prisma", "disconnect_prisma"]
