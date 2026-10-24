import base64
import binascii
import hashlib
import json
import time
from collections.abc import Callable
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.cache import EPOCH_FIELD, CacheTracker, ResponseCache, current_tracker
from app.core.config import settings
from app.integrations.redis import get_response_cache

HIT_HEADER = (b"x-cache", b"HIT")
CACHEABLE_STATUS = 200


def token_expiry(token: str) -> float | None:
    try:
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return float(claims["exp"])
    except IndexError, ValueError, KeyError, TypeError, binascii.Error:
        return None


def bearer_token(scope: Scope) -> str | None:
    for name, value in scope["headers"]:
        if name == b"authorization":
            scheme, _, token = value.decode("latin-1").partition(" ")
            if scheme.lower() != "bearer":
                return None
            return token.strip() or None
    return None


def customer_token(scope: Scope) -> bytes:
    for name, value in scope["headers"]:
        if name == b"x-customer-token":
            return value
    return b""


def entry_key(scope: Scope, token: str | None) -> str:
    parts = [
        (token or "").encode(),
        customer_token(scope),
        scope["path"].encode(),
        scope.get("query_string", b""),
    ]
    request = b"\0".join(parts)
    digest = hashlib.sha256(request).hexdigest()
    return f"{settings.app_name}:{settings.k_revision}:response:{digest}"


def encode_entry(
    status: int, headers: list[tuple[bytes, bytes]], body: bytes, dependencies: dict[str, str]
) -> bytes:
    meta = {
        "status": status,
        "headers": [[name.decode("latin-1"), value.decode("latin-1")] for name, value in headers],
        "dependencies": dependencies,
    }
    return json.dumps(meta, separators=(",", ":")).encode() + b"\n" + body


def decode_entry(
    entry: bytes, versions: dict[str, str]
) -> tuple[int, list[tuple[bytes, bytes]], bytes] | None:
    raw_meta, _, body = entry.partition(b"\n")
    try:
        meta = json.loads(raw_meta)
        dependencies: dict[str, str] = meta["dependencies"]
    except ValueError, KeyError, TypeError:
        return None
    if EPOCH_FIELD not in dependencies or any(
        versions.get(name, "0") != version for name, version in dependencies.items()
    ):
        return None
    headers = [(name.encode("latin-1"), value.encode("latin-1")) for name, value in meta["headers"]]
    return meta["status"], headers, body


class ResponseCacheMiddleware:
    def __init__(
        self, app: ASGIApp, cache_factory: Callable[[], ResponseCache | None] = get_response_cache
    ) -> None:
        self.app = app
        self.cache_factory = cache_factory

    def _cache(self, scope: Scope) -> ResponseCache | None:
        overrides = getattr(scope.get("app"), "dependency_overrides", {})
        return overrides.get(self.cache_factory, self.cache_factory)()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(settings.api_v1_prefix):
            await self.app(scope, receive, send)
            return
        cache = self._cache(scope)
        if cache is None:
            await self.app(scope, receive, send)
            return

        token = bearer_token(scope)
        key = entry_key(scope, token) if scope["method"] == "GET" else None
        versions: dict[str, str] | None = None
        if key is not None:
            entry, versions = await cache.lookup(key)
            cached = decode_entry(entry, versions) if entry and versions else None
            if cached is not None:
                await self._send_cached(send, *cached)
                return

        tracker = CacheTracker()
        reset = current_tracker.set(tracker)
        response: dict[str, Any] = {"status": None, "headers": [], "body": bytearray()}
        invalidated: set[str] = set()

        async def invalidate() -> None:
            pending = tracker.writes - invalidated
            if pending:
                invalidated.update(pending)
                await cache.invalidate(pending)

        async def capture(message: Message) -> None:
            if message["type"] == "http.response.start":
                await invalidate()
                response["status"] = message["status"]
                response["headers"] = list(message.get("headers", []))
            elif message["type"] == "http.response.body" and key is not None:
                response["body"] += message.get("body", b"")
            await send(message)

        try:
            await self.app(scope, receive, capture)
        finally:
            current_tracker.reset(reset)
            await invalidate()

        if key is None or versions is None:
            return
        ttl = self._ttl(tracker, token)
        if response["status"] != CACHEABLE_STATUS or not self._storable(tracker) or ttl <= 0:
            return
        dependencies = {name: versions.get(name, "0") for name in tracker.reads}
        dependencies[EPOCH_FIELD] = versions[EPOCH_FIELD]
        entry = encode_entry(
            response["status"], response["headers"], bytes(response["body"]), dependencies
        )
        await cache.store(key, entry, ttl)

    @staticmethod
    def _storable(tracker: CacheTracker) -> bool:
        return tracker.cacheable and bool(tracker.reads) and not tracker.writes

    @staticmethod
    def _ttl(tracker: CacheTracker, token: str | None) -> int:
        now = time.time()
        limits = [float(settings.cache_ttl_seconds)]
        if token is not None:
            expiry = token_expiry(token)
            if expiry is None:
                return 0
            limits.append(expiry - now)
        if tracker.expires_at is not None:
            limits.append(tracker.expires_at.timestamp() - now)
        return int(min(limits))

    @staticmethod
    async def _send_cached(
        send: Send, status: int, headers: list[tuple[bytes, bytes]], body: bytes
    ) -> None:
        headers = [*headers, HIT_HEADER]
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})
