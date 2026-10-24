from httpx import AsyncClient

from tests.fakes import FakeIdentityProvider
from tests.helpers import API, at, auth, book, create_service, register, slot_at

URL = f"{API}/services"


async def test_create_service(client: AsyncClient, identity: FakeIdentityProvider) -> None:
    token, _ = await register(client, identity, "owner-1")

    service = await create_service(client, token, "  Beard  ", 35.5)

    assert (service["name"], service["price"], service["active"]) == ("Beard", 35.5, True)


async def test_service_requires_registered_barbershop(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token = identity.add_user("someone")
    response = await client.post(URL, json={"name": "Cut", "price": 10}, headers=auth(token))
    assert response.status_code == 403


async def test_service_validation(client: AsyncClient, identity: FakeIdentityProvider) -> None:
    token, _ = await register(client, identity, "owner-1")
    for payload in (
        {"name": "Cut", "price": -1},
        {"name": "Cut", "price": 10.123},
        {"name": " ", "price": 10},
    ):
        response = await client.post(URL, json=payload, headers=auth(token))
        assert response.status_code == 422, payload


async def test_service_names_are_unique_per_barbershop_ignoring_case(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, _ = await register(client, identity, "owner-1")
    other, _ = await register(client, identity, "owner-2")
    await create_service(client, token, "Haircut")

    duplicate = await client.post(URL, json={"name": "HAIRCUT", "price": 1}, headers=auth(token))
    elsewhere = await client.post(URL, json={"name": "Haircut", "price": 1}, headers=auth(other))

    assert duplicate.status_code == 409
    assert elsewhere.status_code == 201


async def test_list_and_filter_services(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, barbershop = await register(client, identity, "owner-1")
    await create_service(client, token, "Haircut")
    beard = await create_service(client, token, "beard")
    await client.patch(f"{URL}/{beard['id']}", json={"active": False}, headers=auth(token))

    everything = await client.get(URL, headers=auth(token))
    active = await client.get(URL, params={"active": True}, headers=auth(token))
    public = await client.get(f"{API}/barbershops/{barbershop['id']}/services")

    assert [item["name"] for item in everything.json()["items"]] == ["beard", "Haircut"]
    assert [item["name"] for item in active.json()["items"]] == ["Haircut"]
    assert [item["name"] for item in public.json()["items"]] == ["Haircut"]
    assert "active" not in public.json()["items"][0]


async def test_other_barbershop_cannot_access_service(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, _ = await register(client, identity, "owner-1")
    other, _ = await register(client, identity, "owner-2")
    service = await create_service(client, token)

    assert (await client.get(f"{URL}/{service['id']}", headers=auth(other))).status_code == 404
    assert (await client.delete(f"{URL}/{service['id']}", headers=auth(other))).status_code == 404


async def test_price_change_keeps_booked_price_and_used_service_cannot_be_deleted(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, barbershop = await register(client, identity, "owner-1")
    service = await create_service(client, token, price=50)
    slot = await slot_at(client, token, at())
    appointment = await book(client, barbershop["id"], slot, [service["id"]])

    updated = await client.patch(f"{URL}/{service['id']}", json={"price": 70}, headers=auth(token))
    reloaded = await client.get(f"{API}/appointments/{appointment['id']}", headers=auth(token))
    deleted = await client.delete(f"{URL}/{service['id']}", headers=auth(token))

    assert updated.json()["price"] == 70
    assert reloaded.json()["items"][0]["price"] == 50
    assert reloaded.json()["total"] == 50
    assert deleted.status_code == 409


async def test_delete_unused_service(client: AsyncClient, identity: FakeIdentityProvider) -> None:
    token, _ = await register(client, identity, "owner-1")
    service = await create_service(client, token)

    response = await client.delete(f"{URL}/{service['id']}", headers=auth(token))

    assert response.status_code == 204
    assert (await client.get(f"{URL}/{service['id']}", headers=auth(token))).status_code == 404
