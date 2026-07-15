import os

from redis.asyncio import Redis


_redis_client: Redis | None = None


def _get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = Redis.from_url(redis_url, decode_responses=True)
    return _redis_client


async def check_rate_limit(key: str, limit: int, window_seconds: int) -> bool:
    """True if this call is within the limit, False if it should be rejected.

    Fixed-window counter (INCR + EXPIRE on first hit) - not perfectly smooth
    at window boundaries, but simple, and good enough to stop bulk abuse of
    an endpoint that sends real email through a real inbox (see
    api/auth.py::request_login, the actual reason this exists).
    """
    redis_client = _get_redis()

    try:
        current = await redis_client.incr(key)
        if current == 1:
            await redis_client.expire(key, window_seconds)
        return current <= limit
    except Exception:
        # Redis being unavailable must never block a legitimate request -
        # same fail-open philosophy as the search cache in services/search.py.
        return True
