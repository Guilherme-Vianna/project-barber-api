from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Appointment
from tests.fakes import FakeIdentityProvider
from tests.helpers import (
    API,
    at,
    auth,
    book,
    create_service,
    customer,
    history_rows,
    iso,
    register,
    slot_at,
)

DEVICE = "a" * 40


async def test_device_follows_reschedules_and_cancels_its_booking(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, barbershop = await register(client, identity, "owner-1")
    service = await create_service(client, token, "Haircut", 50)
    slot = await slot_at(client, token, at(hour=10))
    url = f"{API}/barbershops/{barbershop['id']}/my-booking"
    mine = customer(DEVICE)

    assert (await client.get(url, headers=mine)).status_code == 404
    await book(client, barbershop["id"], slot, [service["id"]], device=DEVICE, last_name="Lima")
    shown = await client.get(url, headers=mine)
    stranger = await client.get(url, headers=customer())
    moved = await client.patch(url, json={"starts_at": iso(at(hour=11))}, headers=mine)
    events = await client.get(f"{url}/events", headers=mine)
    cancelled = await client.delete(url, headers=mine)

    body = shown.json()
    assert body["barbershop_name"] == barbershop["name"]
    assert (body["first_name"], body["last_name"], body["total"]) == ("Carlos", "Lima", 50.0)
    assert "id" not in body
    assert stranger.status_code == 404
    assert moved.status_code == 200
    assert [(item["kind"], item["actor"]) for item in events.json()] == [
        ("booked", "customer"),
        ("rescheduled", "customer"),
    ]
    assert cancelled.status_code == 204
    assert (await client.get(url, headers=mine)).status_code == 404
    rows = await history_rows(session_factory, Appointment)
    assert DEVICE not in {row["customer_token_hash"] for row in rows}


async def test_one_upcoming_booking_per_device(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, barbershop = await register(client, identity, "owner-1")
    other_token, other_shop = await register(client, identity, "owner-2")
    service = await create_service(client, token)
    other_service = await create_service(client, other_token)
    slot = await slot_at(client, token, at(hour=10))
    await slot_at(client, other_token, at(hour=10))
    url = f"{API}/barbershops/{barbershop['id']}/appointments"
    body = {"first_name": "Carlos", "service_ids": [service["id"]]}

    first = await book(client, barbershop["id"], slot, [service["id"]], device=DEVICE)
    second = await client.post(
        url, json={**body, "starts_at": iso(at(hour=12))}, headers=customer(DEVICE)
    )
    elsewhere = await book(client, other_shop["id"], slot, [other_service["id"]], device=DEVICE)
    async with session_factory() as session:
        appointment = await session.get(Appointment, first["id"])
        appointment.starts_at = at(days=0, hour=0) - timedelta(hours=1)
        appointment.ends_at = appointment.starts_at + timedelta(minutes=30)
        await session.commit()
    after_it_passed = await client.post(
        url, json={**body, "starts_at": iso(at(hour=12))}, headers=customer(DEVICE)
    )

    assert second.status_code == 409
    assert elsewhere["id"]
    assert after_it_passed.status_code == 201


async def test_device_token_is_required_and_validated(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, barbershop = await register(client, identity, "owner-1")
    service = await create_service(client, token)
    slot = await slot_at(client, token, at(hour=10))
    url = f"{API}/barbershops/{barbershop['id']}"
    body = {**slot, "first_name": "Carlos", "service_ids": [service["id"]]}

    assert (await client.post(f"{url}/appointments", json=body)).status_code == 422
    assert (
        await client.post(f"{url}/appointments", json=body, headers=customer("short"))
    ).status_code == 422
    assert (await client.get(f"{url}/my-booking")).status_code == 422
    walk_in = await client.post(
        f"{API}/appointments", json={**body, "first_name": "Ana"}, headers=auth(token)
    )
    assert walk_in.status_code == 201
