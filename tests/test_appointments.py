from datetime import datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Appointment, AppointmentItem
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

URL = f"{API}/appointments"


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


async def setup_shop(client: AsyncClient, identity: FakeIdentityProvider, uid: str = "owner-1"):
    token, barbershop = await register(client, identity, uid)
    haircut = await create_service(client, token, "Haircut", 50)
    beard = await create_service(client, token, "Beard", 30.5)
    slot = await slot_at(client, token, at(hour=9))
    return token, barbershop, haircut, beard, slot


async def test_public_booking_snapshots_prices(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, barbershop, haircut, beard, slot = await setup_shop(client, identity)

    appointment = await book(
        client, barbershop["id"], slot, [haircut["id"], beard["id"]], last_name="Lima"
    )

    assert (appointment["first_name"], appointment["last_name"]) == ("Carlos", "Lima")
    assert parse(appointment["starts_at"]) == parse(slot["starts_at"])
    assert parse(appointment["ends_at"]) - parse(appointment["starts_at"]) == timedelta(minutes=30)
    assert sorted((item["name"], item["price"]) for item in appointment["items"]) == [
        ("Beard", 30.5),
        ("Haircut", 50.0),
    ]
    assert appointment["total"] == 80.5
    [row] = await history_rows(session_factory, Appointment)
    assert (row["operation"], row["changed_by"]) == ("insert", None)


async def test_last_name_is_optional(client: AsyncClient, identity: FakeIdentityProvider) -> None:
    _, barbershop, haircut, _, slot = await setup_shop(client, identity)
    appointment = await book(client, barbershop["id"], slot, [haircut["id"]])
    assert appointment["last_name"] is None


async def test_booking_rules(client: AsyncClient, identity: FakeIdentityProvider) -> None:
    token, barbershop, haircut, beard, slot = await setup_shop(client, identity)
    _, _, foreign_service, _, _ = await setup_shop(client, identity, "owner-2")
    past_slot = await slot_at(client, token, at(days=-1))
    free_slot = await slot_at(client, token, at(hour=10))
    await client.patch(f"{API}/services/{beard['id']}", json={"active": False}, headers=auth(token))
    url = f"{API}/barbershops/{barbershop['id']}/appointments"

    def payload(slot: dict, service_ids: list[str]) -> dict:
        return {"starts_at": slot["starts_at"], "first_name": "Carlos", "service_ids": service_ids}

    closed = {"starts_at": iso(at(hour=22))}
    misaligned = {"starts_at": iso(at(hour=10, minute=10))}

    await book(client, barbershop["id"], slot, [haircut["id"]])
    cases = [
        (payload(slot, [haircut["id"]]), 409),
        (payload(closed, [haircut["id"]]), 422),
        (payload(misaligned, [haircut["id"]]), 422),
        ({**payload(free_slot, [haircut["id"]]), "starts_at": "2030-01-01T09:00:00"}, 422),
        (payload(past_slot, [haircut["id"]]), 422),
        (payload(free_slot, [beard["id"]]), 422),
        (payload(free_slot, [foreign_service["id"]]), 422),
        (payload(free_slot, []), 422),
        (payload(free_slot, [haircut["id"], haircut["id"]]), 422),
        ({**payload(free_slot, [haircut["id"]]), "first_name": " "}, 422),
    ]
    for body, expected in cases:
        response = await client.post(url, json=body, headers=customer())
        assert response.status_code == expected, (body, response.text)

    missing_shop = await client.post(
        f"{API}/barbershops/00000000-0000-0000-0000-000000000000/appointments",
        json=payload(free_slot, [haircut["id"]]),
        headers=customer(),
    )
    assert missing_shop.status_code == 404


async def test_owner_creates_lists_and_gets_appointments(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, _, haircut, _, slot = await setup_shop(client, identity)
    other, _, _, _, _ = await setup_shop(client, identity, "owner-2")
    later = await slot_at(client, token, at(days=3))

    response = await client.post(
        URL,
        json={
            "starts_at": later["starts_at"],
            "first_name": "Walk-in",
            "service_ids": [haircut["id"]],
        },
        headers=auth(token),
    )
    first = await client.post(
        URL,
        json={
            "starts_at": slot["starts_at"],
            "first_name": "Early",
            "service_ids": [haircut["id"]],
        },
        headers=auth(token),
    )
    listing = await client.get(URL, headers=auth(token))
    filtered = await client.get(URL, params={"from": iso(at(days=2))}, headers=auth(token))
    others = await client.get(URL, headers=auth(other))
    foreign = await client.get(f"{URL}/{first.json()['id']}", headers=auth(other))

    assert response.status_code == 201
    assert [item["first_name"] for item in listing.json()["items"]] == ["Early", "Walk-in"]
    assert [item["first_name"] for item in filtered.json()["items"]] == ["Walk-in"]
    assert others.json()["total"] == 0
    assert foreign.status_code == 404


async def test_appointments_require_token(client: AsyncClient) -> None:
    assert (await client.get(URL)).status_code == 401


async def test_update_appointment(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, barbershop, haircut, beard, slot = await setup_shop(client, identity)
    other_slot = await slot_at(client, token, at(hour=11))
    taken_slot = await slot_at(client, token, at(hour=12))
    await book(client, barbershop["id"], taken_slot, [haircut["id"]])
    appointment = await book(client, barbershop["id"], slot, [haircut["id"]])
    url = f"{URL}/{appointment['id']}"
    await client.patch(f"{API}/services/{haircut['id']}", json={"price": 99}, headers=auth(token))

    updated = await client.patch(
        url,
        json={
            "starts_at": other_slot["starts_at"],
            "last_name": "Lima",
            "service_ids": [haircut["id"], beard["id"]],
        },
        headers=auth(token),
    )
    taken = await client.patch(
        url, json={"starts_at": taken_slot["starts_at"]}, headers=auth(token)
    )
    null_name = await client.patch(url, json={"first_name": None}, headers=auth(token))
    cleared = await client.patch(
        url, json={"last_name": None, "service_ids": [beard["id"]]}, headers=auth(token)
    )

    body = updated.json()
    assert parse(body["starts_at"]) == parse(other_slot["starts_at"])
    assert sorted((item["name"], item["price"]) for item in body["items"]) == [
        ("Beard", 30.5),
        ("Haircut", 50.0),
    ]
    assert taken.status_code == 409
    assert null_name.status_code == 422
    assert cleared.json()["last_name"] is None
    assert [item["name"] for item in cleared.json()["items"]] == ["Beard"]
    booked = await client.get(
        f"{API}/barbershops/{barbershop['id']}/appointments",
        params={"from": iso(at(hour=9)), "to": iso(at(hour=9, minute=30))},
    )
    assert booked.json()["total"] == 0
    operations = [row["operation"] for row in await history_rows(session_factory, AppointmentItem)]
    assert operations.count("delete") == 1


async def test_cancel_appointment_frees_slot(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, barbershop, haircut, _, slot = await setup_shop(client, identity)
    appointment = await book(client, barbershop["id"], slot, [haircut["id"]])

    response = await client.delete(f"{URL}/{appointment['id']}", headers=auth(token))

    assert response.status_code == 204
    public = await client.get(f"{API}/barbershops/{barbershop['id']}/appointments")
    assert public.json()["total"] == 0
    operations = [row["operation"] for row in await history_rows(session_factory, Appointment)]
    assert operations == ["insert", "delete"]
    await book(client, barbershop["id"], slot, [haircut["id"]])
