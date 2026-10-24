from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.fakes import FakeIdentityProvider

API = "/api/v1"
ZONE = ZoneInfo("America/Sao_Paulo")
FULL_WEEK = [{"weekday": day, "opens_at": "08:00", "closes_at": "20:00"} for day in range(7)]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def at(days: int = 1, hour: int = 9, minute: int = 0) -> datetime:
    base = datetime.now(ZONE).replace(hour=0, minute=0, second=0, microsecond=0)
    return base + timedelta(days=days, hours=hour, minutes=minute)


def iso(moment: datetime) -> str:
    return moment.isoformat()


def barbershop_payload(**overrides: Any) -> dict[str, Any]:
    return {"name": "Barbearia do João", "first_name": "João", "last_name": "Silva", **overrides}


async def history_rows(factory: async_sessionmaker[AsyncSession], model: type) -> list[Any]:
    table = model.__history_table__
    async with factory() as session:
        result = await session.execute(select(table).order_by(table.c.valid_from))
        return list(result.mappings().all())


async def register(
    client: AsyncClient, identity: FakeIdentityProvider, uid: str, **overrides: Any
) -> tuple[str, dict[str, Any]]:
    token = identity.add_user(uid)
    response = await client.post(
        f"{API}/barbershops", json=barbershop_payload(**overrides), headers=auth(token)
    )
    assert response.status_code == 201, response.text
    return token, response.json()


async def create_service(
    client: AsyncClient, token: str, name: str = "Haircut", price: float = 50
) -> dict[str, Any]:
    response = await client.post(
        f"{API}/services", json={"name": name, "price": price}, headers=auth(token)
    )
    assert response.status_code == 201, response.text
    return response.json()


def customer(token: str | None = None) -> dict[str, str]:
    return {"X-Customer-Token": token or uuid4().hex + uuid4().hex}


def window() -> dict[str, str]:
    return {"from": iso(at(days=0, hour=0)), "to": iso(at(days=4, hour=0))}


async def set_schedule(
    client: AsyncClient,
    token: str,
    days: list[dict[str, Any]] | None = None,
    slot_minutes: int = 30,
) -> dict[str, Any]:
    payload = {
        "slot_minutes": slot_minutes,
        "days": FULL_WEEK if days is None else days,
    }
    response = await client.put(f"{API}/schedule", json=payload, headers=auth(token))
    assert response.status_code == 200, response.text
    return response.json()


async def slot_at(client: AsyncClient, token: str, starts_at: datetime) -> dict[str, Any]:
    await set_schedule(client, token)
    return {"starts_at": iso(starts_at)}


async def book(
    client: AsyncClient,
    barbershop_id: str,
    slot: dict[str, Any],
    service_ids: list[str],
    device: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    payload = {
        "starts_at": slot["starts_at"],
        "first_name": "Carlos",
        "service_ids": service_ids,
        **extra,
    }
    response = await client.post(
        f"{API}/barbershops/{barbershop_id}/appointments", json=payload, headers=customer(device)
    )
    assert response.status_code == 201, response.text
    return response.json()
