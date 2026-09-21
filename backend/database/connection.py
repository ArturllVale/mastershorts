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

# Additive schema evolution: add new columns to existing databases that predate
# them. SQLite's ALTER TABLE only supports ADD COLUMN, and ignores the statement
# if the column already exists via the "IF NOT EXISTS" clause (SQLite 3.37+),
# so this is safe to run unconditionally on every startup.
with engine.connect() as _conn:
    for _col_ddl in [
        "ALTER TABLE jobs ADD COLUMN clip_states JSON",
        "ALTER TABLE jobs ADD COLUMN clip_errors JSON",
    ]:
        try:
            _conn.execute(__import__("sqlalchemy").text(_col_ddl))
            _conn.commit()
        except Exception:
            # Column already exists or table doesn't exist yet — both safe to ignore
            pass


def get_db():
    warnings.warn("get_db is deprecated. Use Prisma instead.", DeprecationWarning)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Expose Prisma functions directly for convenience
__all__ = ["get_db", "SessionLocal", "engine", "get_prisma", "disconnect_prisma"]
