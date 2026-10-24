import logging
import time
from collections.abc import Iterable
from functools import lru_cache
from typing import Any
from uuid import uuid4

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.cache import EPOCH_FIELD, ResponseCache
from app.core.config import settings

logger = logging.getLogger(__name__)

REDIS_ERRORS = (RedisError, OSError, TimeoutError)
SOCKET_TIMEOUT_SECONDS = 1.0
INVALIDATE_ATTEMPTS = 2
BACKOFF_SECONDS = 30.0


class RedisResponseCache:
    def __init__(self, url: str, prefix: str, client: Any = None) -> None:
        self._redis = client or Redis.from_url(
            url,
            socket_timeout=SOCKET_TIMEOUT_SECONDS,
            socket_connect_timeout=SOCKET_TIMEOUT_SECONDS,
            health_check_interval=30,
        )
        self._versions_key = f"{prefix}:versions"
        self._retry_at = 0.0
        self._stale = False

    async def lookup(self, key: str) -> tuple[bytes | None, dict[str, str] | None]:
        if self._bypassed():
            return None, None
        try:
            await self._recover()
            async with self._redis.pipeline(transaction=False) as pipe:
                pipe.get(key)
                pipe.hgetall(self._versions_key)
                entry, raw_versions = await pipe.execute()
            versions = _decode(raw_versions)
            if EPOCH_FIELD not in versions:
                await self._redis.hsetnx(self._versions_key, EPOCH_FIELD, uuid4().hex)
                return None, _decode(await self._redis.hgetall(self._versions_key))
        except REDIS_ERRORS as exc:
            self._fail("lookup", exc)
            return None, None
        return entry, versions

    async def store(self, key: str, value: bytes, ttl: int) -> None:
        if self._bypassed():
            return
        try:
            await self._redis.set(key, value, ex=ttl)
        except REDIS_ERRORS as exc:
            self._fail("store", exc)

    async def invalidate(self, names: Iterable[str]) -> None:
        names = sorted(set(names))
        if not names:
            return
        if self._bypassed():
            self._stale = True
            return
        for attempt in range(1, INVALIDATE_ATTEMPTS + 1):
            try:
                async with self._redis.pipeline(transaction=False) as pipe:
                    for name in names:
                        pipe.hincrby(self._versions_key, name, 1)
                    await pipe.execute()
                return
            except REDIS_ERRORS as exc:
                if attempt == INVALIDATE_ATTEMPTS:
                    self._fail(f"invalidation of {names}", exc)

    def _bypassed(self) -> bool:
        return time.monotonic() < self._retry_at

    def _fail(self, action: str, exc: BaseException) -> None:
        logger.warning(
            "Response cache %s failed (%r); bypassing Redis for %.0fs",
            action,
            exc,
            BACKOFF_SECONDS,
        )
        self._retry_at = time.monotonic() + BACKOFF_SECONDS
        self._stale = True

    async def _recover(self) -> None:
        if self._stale:
            await self._redis.hset(self._versions_key, EPOCH_FIELD, uuid4().hex)
            self._stale = False
            logger.info("Response cache reconnected; previous entries invalidated")


def _decode(raw: dict[bytes, bytes]) -> dict[str, str]:
    return {key.decode(): value.decode() for key, value in raw.items()}


@lru_cache
def get_response_cache() -> ResponseCache | None:
    if not settings.redis_url:
        return None
    return RedisResponseCache(settings.redis_url, settings.app_name)
