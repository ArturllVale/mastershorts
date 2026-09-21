import asyncio
from prisma import Prisma

_prisma_client = None

def get_prisma_sync() -> Prisma:
    """Synchronous getter that ensures Prisma is only instantiated once per process,
    and returns an unconnected Prisma instance. It relies on Prisma's auto_register
    and internal connect-on-demand or connect mechanisms where needed."""
    global _prisma_client
    if _prisma_client is None:
        _prisma_client = Prisma(auto_register=True)
    return _prisma_client

async def get_prisma() -> Prisma:
    """Async getter that ensures Prisma is connected."""
    client = get_prisma_sync()
    if not client.is_connected():
        await client.connect()
    return client

async def disconnect_prisma():
    global _prisma_client
    if _prisma_client is not None and _prisma_client.is_connected():
        await _prisma_client.disconnect()
        _prisma_client = None
