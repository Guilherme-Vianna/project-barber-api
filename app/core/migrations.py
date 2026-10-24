import asyncio
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

logger = logging.getLogger(__name__)

ALEMBIC_DIRECTORY = Path(__file__).resolve().parents[2] / "alembic"


def alembic_config() -> Config:
    config = Config()
    config.set_main_option("script_location", str(ALEMBIC_DIRECTORY))
    return config


async def ensure_database() -> None:
    url = make_url(settings.database_url)
    name = url.database
    if not name:
        return
    admin_engine = create_async_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    try:
        async with admin_engine.connect() as connection:
            exists = await connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}
            )
            if not exists:
                logger.info("Creating database %s", name)
                quoted = connection.dialect.identifier_preparer.quote(name)
                await connection.execute(text(f"CREATE DATABASE {quoted}"))
    finally:
        await admin_engine.dispose()


async def run_migrations() -> None:
    await ensure_database()
    logger.info("Applying pending database migrations")
    await asyncio.to_thread(command.upgrade, alembic_config(), "head")
    logger.info("Database schema is up to date")
