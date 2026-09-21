import asyncio
from prisma import Prisma

_prisma_client = None

async def get_prisma() -> Prisma:
    global _prisma_client
    if _prisma_client is None:
        _prisma_client = Prisma(auto_register=True)
        await _prisma_client.connect()
    return _prisma_client

async def disconnect_prisma():
    global _prisma_client
    if _prisma_client is not None:
        await _prisma_client.disconnect()
        _prisma_client = None
