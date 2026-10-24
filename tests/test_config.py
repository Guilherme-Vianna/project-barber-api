import pytest

from app.core.config import Settings, to_async_database_url

NEON_URL = (
    "postgresql://user:p%40ss@ep-billowing-king-b6xvbmza-pooler.c-2.sa-east-1.aws.neon.tech"
    "/neondb?sslmode=require&channel_binding=require"
)


def test_neon_url_is_converted_for_asyncpg() -> None:
    assert to_async_database_url(NEON_URL) == (
        "postgresql+asyncpg://user:p%40ss@ep-billowing-king-b6xvbmza-pooler.c-2.sa-east-1.aws.neon.tech"
        "/neondb?ssl=require"
    )


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgres://u:p@host/db", "postgresql+asyncpg://u:p@host/db?ssl=require"),
        ("postgres://u:p@localhost/db", "postgresql+asyncpg://u:p@localhost/db"),
        ("postgresql+asyncpg://u:p@db:5432/db", "postgresql+asyncpg://u:p@db:5432/db"),
        (
            "postgresql://u:p@host/db?sslmode=disable",
            "postgresql+asyncpg://u:p@host/db?ssl=disable",
        ),
        (
            "postgresql://u:p@host/db?ssl=verify-full&sslmode=require",
            "postgresql+asyncpg://u:p@host/db?ssl=verify-full",
        ),
    ],
)
def test_other_urls(url: str, expected: str) -> None:
    assert to_async_database_url(url) == expected


def test_settings_normalize_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", NEON_URL)
    assert Settings().database_url.startswith("postgresql+asyncpg://")


def test_settings_ignore_surrounding_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_ECHO", "false\r\n")
    monkeypatch.setenv("DB_POOL_SIZE", " 7\r\n")
    monkeypatch.setenv("FIREBASE_PROJECT_ID", " \r\n")
    monkeypatch.setenv("DATABASE_URL", f"{NEON_URL}\r\n")

    configured = Settings(_env_file=None)

    assert configured.db_echo is False
    assert configured.db_pool_size == 7
    assert configured.firebase_project_id is None
    assert configured.database_url.endswith("/neondb?ssl=require")
