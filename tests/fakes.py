import base64
import json
import time
from collections.abc import Iterable
from uuid import uuid4

from app.core.auth import AuthenticatedUser
from app.core.cache import EPOCH_FIELD
from app.core.exceptions import UnauthorizedError

TOKEN_LIFETIME_SECONDS = 3600


def fake_token(uid: str, expires_at: float | None = None) -> str:
    claims = {"uid": uid, "exp": expires_at or time.time() + TOKEN_LIFETIME_SECONDS}
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"header.{payload}.signature"


class FakeIdentityProvider:
    def __init__(self) -> None:
        self.tokens: dict[str, str] = {}
        self.names: dict[str, str | None] = {}

    def add_user(self, uid: str, name: str | None = None) -> str:
        token = fake_token(uid)
        self.tokens[token] = uid
        self.names[uid] = name
        return token

    async def verify_token(self, token: str) -> AuthenticatedUser:
        uid = self.tokens.get(token)
        if uid is None:
            raise UnauthorizedError("Invalid or expired authentication token")
        return AuthenticatedUser(uid=uid, email=f"{uid}@example.com", name=self.names[uid])


class FakeResponseCache:
    def __init__(self) -> None:
        self.entries: dict[str, bytes] = {}
        self.ttls: dict[str, int] = {}
        self.versions: dict[str, int | str] = {}
        self.available = True

    async def lookup(self, key: str) -> tuple[bytes | None, dict[str, str] | None]:
        if not self.available:
            return None, None
        if EPOCH_FIELD not in self.versions:
            self.versions[EPOCH_FIELD] = uuid4().hex
            return None, self._versions()
        return self.entries.get(key), self._versions()

    async def store(self, key: str, value: bytes, ttl: int) -> None:
        if self.available:
            self.entries[key] = value
            self.ttls[key] = ttl

    async def invalidate(self, names: Iterable[str]) -> None:
        if not self.available:
            return
        for name in names:
            current = self.versions.get(name, 0)
            assert isinstance(current, int)
            self.versions[name] = current + 1

    def _versions(self) -> dict[str, str]:
        return {name: str(value) for name, value in self.versions.items()}
