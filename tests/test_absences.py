from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Absence, Appointment, AppointmentItem
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

URL = f"{API}/absences"


def period(start, end) -> dict:
    return {"starts_at": iso(start), "ends_at": iso(end)}


async def test_absence_cancels_appointments_and_blocks_the_interval(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, barbershop = await register(client, identity, "owner-1")
    service = await create_service(client, token)
    await set_schedule(client, token)
    inside = {"starts_at": iso(at(hour=10))}
    edge = {"starts_at": iso(at(hour=11))}
    outside = {"starts_at": iso(at(hour=14))}
    for slot in (inside, edge, outside):
        await book(client, barbershop["id"], slot, [service["id"]])

    response = await client.post(URL, json=period(at(hour=9), at(hour=11)), headers=auth(token))

    assert response.status_code == 201
    assert response.json()["cancelled_appointments"] == 1
    remaining = await client.get(f"{API}/appointments", headers=auth(token))
    assert remaining.json()["total"] == 2
    url = f"{API}/barbershops/{barbershop['id']}/appointments"
    blocked = {"first_name": "Ana", "service_ids": [service["id"]]}
    assert (
        await client.post(url, headers=customer(), json={**blocked, **inside})
    ).status_code == 422
    assert (
        await client.post(url, headers=customer(), json={**blocked, "starts_at": iso(at(hour=9))})
    ).status_code == 422
    assert (
        await client.post(url, headers=customer(), json={**blocked, "starts_at": iso(at(hour=12))})
    ).status_code == 201
    for model in (Appointment, AppointmentItem):
        operations = [row["operation"] for row in await history_rows(session_factory, model)]
        assert operations.count("delete") == 1, model.__name__
    [row] = await history_rows(session_factory, Absence)
    assert (row["operation"], row["changed_by"]) == ("insert", "owner-1")


async def test_absence_validation_and_access(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, _ = await register(client, identity, "owner-1")
    no_shop = identity.add_user("no-shop")

    invalid = [
        period(at(hour=10), at(hour=10)),
        period(at(hour=11), at(hour=10)),
        {"starts_at": "2030-01-01T09:00:00", "ends_at": "2030-01-01T10:00:00"},
        period(at(days=-2), at(days=-1)),
    ]
    for body in invalid:
        response = await client.post(URL, json=body, headers=auth(token))
        assert response.status_code == 422, body
    valid = period(at(hour=10), at(hour=11))
    assert (await client.post(URL, json=valid)).status_code == 401
    assert (await client.post(URL, json=valid, headers=auth(no_shop))).status_code == 403
    assert (await client.get(URL)).status_code == 401


async def test_list_and_remove_absences(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, barbershop = await register(client, identity, "owner-1")
    other, _ = await register(client, identity, "owner-2")
    await set_schedule(client, token)
    first = (
        await client.post(
            URL, json=period(at(days=1, hour=9), at(days=1, hour=12)), headers=auth(token)
        )
    ).json()
    await client.post(
        URL, json=period(at(days=3, hour=9), at(days=3, hour=12)), headers=auth(token)
    )

    everything = await client.get(URL, headers=auth(token))
    day_one = await client.get(
        URL,
        params={"from": iso(at(days=1, hour=0)), "to": iso(at(days=2, hour=0))},
        headers=auth(token),
    )
    public = await client.get(f"{API}/barbershops/{barbershop['id']}/absences")
    foreign = await client.delete(f"{URL}/{first['id']}", headers=auth(other))
    removed = await client.delete(f"{URL}/{first['id']}", headers=auth(token))
    again = await client.delete(f"{URL}/{first['id']}", headers=auth(token))

    assert everything.json()["total"] == 2
    assert [item["id"] for item in day_one.json()["items"]] == [first["id"]]
    assert set(public.json()["items"][0]) == {"starts_at", "ends_at"}
    assert public.json()["total"] == 2
    assert (await client.get(URL, headers=auth(other))).json()["total"] == 0
    assert foreign.status_code == 404
    assert removed.status_code == 204
    assert again.status_code == 404
    assert (await client.get(URL, headers=auth(token))).json()["total"] == 1
