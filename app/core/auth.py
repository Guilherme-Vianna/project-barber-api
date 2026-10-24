from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    uid: str
    email: str | None = None
    name: str | None = None
    claims: dict[str, Any] = field(default_factory=dict)


class IdentityProvider(Protocol):
    async def verify_token(self, token: str) -> AuthenticatedUser: ...
