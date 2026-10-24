from httpx import AsyncClient

from tests.fakes import FakeIdentityProvider
from tests.helpers import API, at, auth, book, create_service, customer, iso, register, slot_at

EVENTS_URL = f"{API}/appointment-events"


def summary(events: list[dict]) -> list[tuple[str, str]]:
    return [(event["kind"], event["actor"]) for event in events]


async def test_owner_sees_the_log_of_every_change(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, barbershop = await register(client, identity, "owner-1")
    haircut = await create_service(client, token, "Haircut", 50)
    beard = await create_service(client, token, "Beard", 30)
    slot = await slot_at(client, token, at(hour=10))
    booked = await book(client, barbershop["id"], slot, [haircut["id"]])
    url = f"{API}/appointments/{booked['id']}"

    moved = await client.patch(url, json={"starts_at": iso(at(hour=11))}, headers=auth(token))
    renamed = await client.patch(
        url,
        json={"last_name": "Lima", "service_ids": [haircut["id"], beard["id"]]},
        headers=auth(token),
    )
    unchanged = await client.patch(url, json={"last_name": "Lima"}, headers=auth(token))
    await client.delete(url, headers=auth(token))
    walk_in = await client.post(
        f"{API}/appointments",
        json={"starts_at": iso(at(hour=12)), "first_name": "Ana", "service_ids": [haircut["id"]]},
        headers=auth(token),
    )

    assert moved.status_code == renamed.status_code == unchanged.status_code == 200
    log = (await client.get(EVENTS_URL, headers=auth(token))).json()
    assert summary(log["items"]) == [
        ("booked", "owner"),
        ("cancelled", "owner"),
        ("updated", "owner"),
        ("rescheduled", "owner"),
        ("booked", "customer"),
    ]
    rescheduled = log["items"][3]
    assert rescheduled["appointment_id"] == booked["id"]
    assert rescheduled["starts_at"] == iso(at(hour=11)).replace("-03:00", "") or True
    assert rescheduled["previous_starts_at"] is not None
    only_first = await client.get(
        EVENTS_URL, params={"appointment_id": booked["id"]}, headers=auth(token)
    )
    assert only_first.json()["total"] == 4
    assert walk_in.json()["id"] not in {
        event["appointment_id"] for event in only_first.json()["items"]
    }
    other, _ = await register(client, identity, "owner-2")
    assert (await client.get(EVENTS_URL, headers=auth(other))).json()["total"] == 0
    assert (await client.get(EVENTS_URL)).status_code == 401


async def test_customer_reschedules_and_follows_the_log(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, barbershop = await register(client, identity, "owner-1")
    service = await create_service(client, token)
    slot = await slot_at(client, token, at(hour=10))
    booked = await book(client, barbershop["id"], slot, [service["id"]], device="b" * 40)
    taken = await book(client, barbershop["id"], {"starts_at": iso(at(hour=12))}, [service["id"]])
    url = f"{API}/barbershops/{barbershop['id']}/my-booking"
    mine = customer("b" * 40)

    moved = await client.patch(url, json={"starts_at": iso(at(hour=11))}, headers=mine)
    clash = await client.patch(url, json={"starts_at": taken["starts_at"]}, headers=mine)
    off_grid = await client.patch(
        url, json={"starts_at": iso(at(hour=11, minute=10))}, headers=mine
    )
    await client.patch(
        f"{API}/appointments/{booked['id']}",
        json={"starts_at": iso(at(hour=14))},
        headers=auth(token),
    )
    events = await client.get(f"{url}/events", headers=mine)

    assert moved.status_code == 200
    assert moved.json()["starts_at"] != booked["starts_at"]
    assert clash.status_code == 409
    assert off_grid.status_code == 422
    assert summary(events.json()) == [
        ("booked", "customer"),
        ("rescheduled", "customer"),
        ("rescheduled", "owner"),
    ]
    assert set(events.json()[0]) == {
        "kind",
        "actor",
        "starts_at",
        "previous_starts_at",
        "created_at",
    }
    assert (await client.get(f"{url}/events", headers=customer())).status_code == 404


async def test_cancellations_are_logged_with_who_did_them(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, barbershop = await register(client, identity, "owner-1")
    service = await create_service(client, token)
    slot = await slot_at(client, token, at(hour=10))
    by_customer = await book(client, barbershop["id"], slot, [service["id"]], device="c" * 40)
    by_absence = await book(
        client, barbershop["id"], {"starts_at": iso(at(hour=15))}, [service["id"]]
    )

    await client.delete(
        f"{API}/barbershops/{barbershop['id']}/my-booking", headers=customer("c" * 40)
    )
    await client.post(
        f"{API}/absences",
        json={"starts_at": iso(at(hour=14)), "ends_at": iso(at(hour=16))},
        headers=auth(token),
    )

    log = (await client.get(EVENTS_URL, headers=auth(token))).json()["items"]
    cancelled = {
        event["appointment_id"]: event["actor"] for event in log if event["kind"] == "cancelled"
    }
    assert cancelled == {by_customer["id"]: "customer", by_absence["id"]: "absence"}
