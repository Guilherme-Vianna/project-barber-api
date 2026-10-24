from collections.abc import AsyncIterator
from uuid import uuid7

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app import main
from app.core.config import settings
from app.core.migrations import alembic_config, run_migrations
from tests.conftest import TEST_DATABASE_URL


@pytest.fixture
async def empty_database(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[str]:
    base = make_url(TEST_DATABASE_URL)
    name = f"migrations_{uuid7().hex}"
    admin = create_async_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    async with admin.connect() as connection:
        await connection.execute(text(f'CREATE DATABASE "{name}"'))
    url = base.set(database=name).render_as_string(hide_password=False)
    monkeypatch.setattr(settings, "database_url", url)
    yield url
    async with admin.connect() as connection:
        await connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    await admin.dispose()


async def current_revision(url: str) -> str | None:
    engine = create_async_engine(url)
    async with engine.connect() as connection:
        revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        has_barbershops = await connection.scalar(text("SELECT to_regclass('public.barbershops')"))
    await engine.dispose()
    assert has_barbershops is not None
    return revision


def head_revision() -> str | None:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


async def test_migrates_empty_database_to_head(empty_database: str) -> None:
    await run_migrations()
    await run_migrations()

    assert await current_revision(empty_database) == head_revision()


async def test_startup_runs_migrations_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    async def fake_run_migrations() -> None:
        calls.append(True)

    monkeypatch.setattr(main, "run_migrations", fake_run_migrations)
    for enabled, expected in ((True, 1), (False, 1)):
        monkeypatch.setattr(settings, "run_migrations_on_startup", enabled)
        async with main.lifespan(main.app):
            pass
        assert len(calls) == expected
