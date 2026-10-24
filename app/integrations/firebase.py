import asyncio
import base64
import json
import os
from functools import lru_cache

import firebase_admin
from firebase_admin import auth, credentials
from firebase_admin.exceptions import FirebaseError

from app.core.auth import AuthenticatedUser
from app.core.config import settings
from app.core.exceptions import IdentityProviderError, UnauthorizedError


class FirebaseIdentityProvider:
    def __init__(
        self,
        project_id: str | None,
        credentials_path: str | None = None,
        emulator_host: str | None = None,
        credentials_base64: str | None = None,
    ) -> None:
        if emulator_host:
            os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = emulator_host
        credential = None
        if credentials_base64:
            info = json.loads(base64.b64decode(credentials_base64))
            credential = credentials.Certificate(info)
        elif credentials_path:
            credential = credentials.Certificate(credentials_path)
        options = {"projectId": project_id} if project_id else None
        try:
            self._app = firebase_admin.get_app()
        except ValueError:
            self._app = firebase_admin.initialize_app(credential, options=options)

    async def verify_token(self, token: str) -> AuthenticatedUser:
        try:
            decoded = await asyncio.to_thread(auth.verify_id_token, token, self._app)
        except (auth.InvalidIdTokenError, ValueError) as exc:
            raise UnauthorizedError("Invalid or expired authentication token") from exc
        except (auth.CertificateFetchError, FirebaseError) as exc:
            raise IdentityProviderError("Identity provider is unavailable") from exc
        return AuthenticatedUser(
            uid=decoded["uid"],
            email=decoded.get("email"),
            name=decoded.get("name"),
            claims=decoded,
        )


@lru_cache
def get_identity_provider() -> FirebaseIdentityProvider:
    return FirebaseIdentityProvider(
        settings.firebase_project_id,
        settings.google_application_credentials,
        settings.firebase_auth_emulator_host,
        settings.firebase_credentials_base64,
    )
