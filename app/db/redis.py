from typing import AsyncGenerator

import aioredis

from app.core.config import settings

# Create a global Redis client instance.
# decode_responses=True to get Python strings instead of bytes.
redis_client = aioredis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
)


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """
    FastAPI dependency that yields a Redis client.

    Yields:
        aioredis.Redis: shared Redis connection.

    Since aioredis maintains its own connection pool internally,
    we simply yield the singleton instance.
    """
    yield redis_client
