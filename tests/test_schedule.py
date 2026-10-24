from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import WorkingHours
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
    set_schedule,
)

URL = f"{API}/schedule"


def hours(weekday: int, opens_at: str = "09:00", closes_at: str = "10:30") -> dict:
    return {"weekday": weekday, "opens_at": opens_at, "closes_at": closes_at}


def payload(**overrides) -> dict:
    return {
        "slot_minutes": 30,
        "days": [hours(0)],
        **overrides,
    }


async def test_schedule_starts_empty(client: AsyncClient, identity: FakeIdentityProvider) -> None:
    token, _ = await register(client, identity, "owner-1")

    response = await client.get(URL, headers=auth(token))

    assert response.json() == {"slot_minutes": 30, "days": []}


async def test_replace_schedule(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, _ = await register(client, identity, "owner-1")
    other, _ = await register(client, identity, "owner-2")

    first = await set_schedule(client, token, [hours(0), hours(2)], slot_minutes=45)
    second = await set_schedule(client, token, [hours(0, closes_at="12:00")], slot_minutes=20)
    reloaded = await client.get(URL, headers=auth(token))

    assert [day["weekday"] for day in first["days"]] == [0, 2]
    assert reloaded.json() == second
    assert second["slot_minutes"] == 20
    assert second["days"] == [{"weekday": 0, "opens_at": "09:00:00", "closes_at": "12:00:00"}]
    assert (await client.get(URL, headers=auth(other))).json()["days"] == []
    operations = [row["operation"] for row in await history_rows(session_factory, WorkingHours)]
    assert operations == ["insert", "insert", "delete", "update"]


async def test_schedule_validation(client: AsyncClient, identity: FakeIdentityProvider) -> None:
    token, _ = await register(client, identity, "owner-1")
    base = payload()
    invalid = [
        {**base, "days": [hours(0, "10:00", "10:00")]},
        {**base, "days": [hours(0, "10:00", "09:00")]},
        {**base, "days": [hours(0), hours(0, closes_at="11:00")]},
        {**base, "days": [hours(7)]},
        {**base, "slot_minutes": 4},
        {**base, "slot_minutes": 481},
        {key: value for key, value in base.items() if key != "slot_minutes"},
    ]
    for body in invalid:
        response = await client.put(URL, json=body, headers=auth(token))
        assert response.status_code == 422, body
    assert (await client.put(URL, json=base, headers=auth(token))).status_code == 200


async def test_schedule_requires_token_and_barbershop(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    no_shop = identity.add_user("no-shop")

    assert (await client.get(URL)).status_code == 401
    assert (await client.put(URL, json=payload())).status_code == 401
    assert (await client.get(URL, headers=auth(no_shop))).status_code == 403
    assert (await client.put(URL, json=payload(), headers=auth(no_shop))).status_code == 403


async def test_public_schedule(client: AsyncClient, identity: FakeIdentityProvider) -> None:
    token, barbershop = await register(client, identity, "owner-1")
    saved = await set_schedule(client, token, [hours(1)], slot_minutes=40)

    public = await client.get(f"{API}/barbershops/{barbershop['id']}/schedule")
    missing = await client.get(f"{API}/barbershops/00000000-0000-0000-0000-000000000000/schedule")

    assert public.json() == saved
    assert missing.status_code == 404


async def test_public_booked_times_hide_personal_data(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, barbershop = await register(client, identity, "owner-1")
    service = await create_service(client, token)
    await set_schedule(client, token)
    first = {"starts_at": iso(at(days=1, hour=9))}
    second = {"starts_at": iso(at(days=3, hour=9))}
    await book(client, barbershop["id"], second, [service["id"]])
    await book(client, barbershop["id"], first, [service["id"]])
    url = f"{API}/barbershops/{barbershop['id']}/appointments"

    everything = await client.get(url)
    day_one = await client.get(
        url, params={"from": iso(at(days=1, hour=0)), "to": iso(at(days=2, hour=0))}
    )
    page = await client.get(url, params={"limit": 1, "offset": 1})

    assert everything.json()["total"] == 2
    assert set(everything.json()["items"][0]) == {"starts_at", "ends_at"}
    assert day_one.json()["total"] == 1
    assert len(page.json()["items"]) == 1 and page.json()["total"] == 2


async def test_booking_follows_the_schedule(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, barbershop = await register(client, identity, "owner-1")
    service = await create_service(client, token)
    url = f"{API}/barbershops/{barbershop['id']}/appointments"
    target = at(days=1, hour=9)
    body = {"first_name": "Carlos", "service_ids": [service["id"]]}

    async def attempt(starts_at) -> int:
        return (
            await client.post(url, json={**body, "starts_at": iso(starts_at)}, headers=customer())
        ).status_code

    assert await attempt(target) == 422

    await set_schedule(client, token, [hours(target.weekday())], slot_minutes=45)
    assert await attempt(target) == 201
    assert await attempt(target + timedelta(minutes=45)) == 201
    assert await attempt(target + timedelta(minutes=90)) == 422
    assert await attempt(target + timedelta(minutes=30)) == 422
    assert await attempt(target - timedelta(minutes=45)) == 422
    assert await attempt(target + timedelta(days=1)) == 422

    await set_schedule(client, token, [hours(target.weekday()), hours((target.weekday() + 1) % 7)])
    assert await attempt(target + timedelta(days=7)) == 201
    assert await attempt(target + timedelta(days=700)) == 201
    assert await attempt(target + timedelta(days=2)) == 422
