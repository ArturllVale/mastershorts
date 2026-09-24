import asyncio
import os
from prisma import Prisma

os.environ['DATABASE_URL'] = 'file:./dev.db'

async def main():
    p = Prisma()
    await p.connect()
    print('Connected')
    await p.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
