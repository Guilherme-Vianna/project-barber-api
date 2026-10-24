from typing import Any

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.cache import EPOCH_FIELD
from app.integrations import redis as redis_module
from app.integrations.redis import BACKOFF_SECONDS, RedisResponseCache


class FakePipeline:
    def __init__(self, client: FakeRedisClient) -> None:
        self.client = client
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def __aenter__(self) -> FakePipeline:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    def __getattr__(self, name: str) -> Any:
        return lambda *args: self.calls.append((name, args))

    async def execute(self) -> list[Any]:
        return [await getattr(self.client, name)(*args) for name, args in self.calls]


class FakeRedisClient:
    def __init__(self) -> None:
        self.down = False
        self.calls = 0
        self.values: dict[str, bytes] = {}
        self.hashes: dict[str, dict[bytes, bytes]] = {}

    def pipeline(self, transaction: bool = False) -> FakePipeline:
        return FakePipeline(self)

    def _touch(self) -> None:
        self.calls += 1
        if self.down:
            raise RedisConnectionError("Redis is down")

    async def get(self, key: str) -> bytes | None:
        self._touch()
        return self.values.get(key)

    async def set(self, key: str, value: bytes, ex: int) -> None:
        self._touch()
        self.values[key] = value

    async def hgetall(self, key: str) -> dict[bytes, bytes]:
        self._touch()
        return dict(self.hashes.get(key, {}))

    async def hset(self, key: str, field: str, value: str) -> None:
        self._touch()
        self.hashes.setdefault(key, {})[field.encode()] = value.encode()

    async def hsetnx(self, key: str, field: str, value: str) -> None:
        self._touch()
        self.hashes.setdefault(key, {}).setdefault(field.encode(), value.encode())

    async def hincrby(self, key: str, field: str, amount: int) -> None:
        self._touch()
        fields = self.hashes.setdefault(key, {})
        fields[field.encode()] = str(int(fields.get(field.encode(), b"0")) + amount).encode()


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    now = [1000.0]
    monkeypatch.setattr(redis_module.time, "monotonic", lambda: now[0])
    return now


def make_cache() -> tuple[RedisResponseCache, FakeRedisClient]:
    client = FakeRedisClient()
    return RedisResponseCache("redis://unused", "test", client=client), client


async def test_failure_bypasses_redis_during_backoff(clock: list[float]) -> None:
    cache, client = make_cache()
    client.down = True

    assert await cache.lookup("key") == (None, None)
    calls = client.calls
    assert await cache.lookup("key") == (None, None)
    await cache.store("key", b"value", 60)
    await cache.invalidate(["services"])

    assert client.calls == calls


async def test_recovery_invalidates_entries_from_before_the_outage(clock: list[float]) -> None:
    cache, client = make_cache()
    _, before = await cache.lookup("key")
    await cache.store("key", b"value", 60)
    client.down = True
    await cache.invalidate(["services"])

    client.down = False
    clock[0] += BACKOFF_SECONDS + 1
    entry, after = await cache.lookup("key")

    assert before is not None and after is not None
    assert entry == b"value"
    assert after[EPOCH_FIELD] != before[EPOCH_FIELD]


async def test_writes_skipped_during_backoff_still_invalidate_on_recovery(
    clock: list[float],
) -> None:
    cache, client = make_cache()
    _, before = await cache.lookup("key")
    client.down = True
    await cache.lookup("key")
    client.down = False
    await cache.invalidate(["services"])

    clock[0] += BACKOFF_SECONDS + 1
    _, after = await cache.lookup("key")

    assert before is not None and after is not None
    assert after[EPOCH_FIELD] != before[EPOCH_FIELD]
