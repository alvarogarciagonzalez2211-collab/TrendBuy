import logging
import os
from datetime import date, timedelta

from redis.asyncio import Redis


logger = logging.getLogger(__name__)

# Outbound-click counters back the monetization decisions (which store's
# affiliate program to prioritize, whether a network is worth joining) - they
# are operational metrics, not user data: no user id, no product, just
# store + surface + day. Redis-only on purpose: losing them on a flush is
# acceptable, adding a Postgres table + migration for this is not (yet).
CLICK_KEY_PREFIX = "trendbuy:clicks:"
CLICK_TTL_SECONDS = 90 * 24 * 3600

_redis_client: Redis | None = None


def _get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = Redis.from_url(redis_url, decode_responses=True)
    return _redis_client


def _day_key(day: date) -> str:
    return f"{CLICK_KEY_PREFIX}{day.isoformat()}"


def normalize_store(store: str) -> str:
    return " ".join(store.split()).strip().lower()[:60] or "unknown"


async def record_click(store: str, source: str = "web") -> None:
    # Fire-and-forget: the frontend sends this as a beacon while the user is
    # already navigating away to the store - it must never fail loudly, and
    # Redis being down just means one uncounted click.
    field = f"{normalize_store(store)}|{source[:20]}"
    key = _day_key(date.today())
    try:
        redis_client = _get_redis()
        await redis_client.hincrby(key, field, 1)
        await redis_client.expire(key, CLICK_TTL_SECONDS)
    except Exception as exc:
        logger.warning("Click metric write failed for %s: %s", field, exc)


async def get_click_stats(days: int = 30) -> dict[str, object]:
    # Aggregated per store and per day for the admin stats endpoint - small
    # enough (stores x days hash fields) to assemble in one pass.
    today = date.today()
    per_day: dict[str, dict[str, int]] = {}
    per_store: dict[str, int] = {}
    total = 0

    redis_client = _get_redis()
    for offset in range(days):
        day = today - timedelta(days=offset)
        try:
            fields = await redis_client.hgetall(_day_key(day))
        except Exception as exc:
            logger.warning("Click metric read failed for %s: %s", day, exc)
            break

        if not fields:
            continue

        day_bucket: dict[str, int] = {}
        for field, raw_count in fields.items():
            store = field.split("|", 1)[0]
            count = int(raw_count)
            day_bucket[store] = day_bucket.get(store, 0) + count
            per_store[store] = per_store.get(store, 0) + count
            total += count
        per_day[day.isoformat()] = day_bucket

    return {
        "days": days,
        "total_clicks": total,
        "clicks_by_store": dict(sorted(per_store.items(), key=lambda item: -item[1])),
        "clicks_by_day": per_day,
    }
