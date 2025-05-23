# app/db/redis.py

import aioredis

from app.core.config import settings

# Create a global Redis client instance.
redis_client = aioredis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
)


async def get_redis():
    """
    FastAPI dependency that yields a Redis client.
    Ensures Redis is alive before yielding client.
    """
    await redis_client.ping()
    yield redis_client
