from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Railway internal postgres needs ssl=disable
if "railway.internal" in DATABASE_URL:
    connect_args = {"ssl": False}
else:
    connect_args = {}

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args=connect_args,
)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

_redis = None

async def get_redis():
    global _redis
    if _redis is None:
        import redis.asyncio as aioredis
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        _redis = await aioredis.from_url(redis_url, decode_responses=True)
    return _redis
