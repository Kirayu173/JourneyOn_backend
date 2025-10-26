from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Optional

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_raw_client() -> Optional[Redis]:
    url = settings.REDIS_URL
    if not url:
        return None
    return Redis.from_url(url, decode_responses=True)


def get_client() -> Optional[Redis]:
    try:
        return _get_raw_client()
    except RedisError:
        logger.exception("Redis connection initialization failed")
        return None


async def ping() -> bool:
    client = get_client()
    if client is None:
        return False
    try:
        return bool(await client.ping())
    except RedisError:
        logger.warning("Redis ping failed", exc_info=True)
        return False


async def get_value(key: str) -> Optional[str]:
    client = get_client()
    if client is None:
        return None
    try:
        return await client.get(key)
    except RedisError:
        logger.warning("Redis GET failed", exc_info=True)
        return None


async def set_value(key: str, value: str, *, expire_seconds: int | None = None) -> None:
    client = get_client()
    if client is None:
        return
    try:
        await client.set(key, value, ex=expire_seconds)
    except RedisError:
        logger.warning("Redis SET failed", exc_info=True)


async def delete_value(key: str) -> None:
    client = get_client()
    if client is None:
        return
    try:
        await client.delete(key)
    except RedisError:
        logger.warning("Redis DEL failed", exc_info=True)


async def incr(key: str, *, expire_seconds: int | None = None) -> Optional[int]:
    client = get_client()
    if client is None:
        return None
    try:
        pipe = client.pipeline(True)
        pipe.incr(key, 1)
        if expire_seconds:
            pipe.expire(key, expire_seconds, nx=True)
        result: list[Any] = await pipe.execute()
        return int(result[0]) if result else None
    except RedisError:
        logger.warning("Redis INCR failed", exc_info=True)
        return None


__all__ = [
    "get_client",
    "ping",
    "get_value",
    "set_value",
    "delete_value",
    "incr",
]
