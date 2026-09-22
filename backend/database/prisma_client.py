import asyncio
try:
    from prisma import Prisma
    HAS_PRISMA = True
except (ImportError, ModuleNotFoundError, AttributeError):
    Prisma = None
    HAS_PRISMA = False

import os

_prisma_client = None

def _ensure_database_url():
    if not os.environ.get("DATABASE_URL"):
        dev_db = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dev.db")).replace("\\", "/")
        os.environ["DATABASE_URL"] = f"file:{dev_db}"

def get_prisma_sync():
    """Synchronous getter that ensures Prisma is only instantiated once per process,
    and returns an unconnected Prisma instance. It relies on Prisma's auto_register
    and internal connect-on-demand or connect mechanisms where needed."""
    global _prisma_client
    if not HAS_PRISMA:
        return None
    _ensure_database_url()
    if _prisma_client is None:
        try:
            from prisma import _registry
            if _registry._registered_client is not None:
                _prisma_client = _registry._registered_client
        except Exception:
            pass
        if _prisma_client is None:
            _prisma_client = Prisma(auto_register=True)
    return _prisma_client

async def get_prisma():
    """Async getter that ensures Prisma is connected."""
    client = get_prisma_sync()
    if client and not client.is_connected():
        await client.connect()
    return client

async def disconnect_prisma():
    global _prisma_client
    if _prisma_client is not None and getattr(_prisma_client, "is_connected", lambda: False)():
        await _prisma_client.disconnect()
        _prisma_client = None
