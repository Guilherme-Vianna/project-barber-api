from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Appointment, AppointmentItem, Barbershop, Service, WorkingHours
from tests.fakes import FakeIdentityProvider
from tests.helpers import (
    API,
    at,
    auth,
    barbershop_payload,
    book,
    create_service,
    history_rows,
    iso,
    register,
    set_schedule,
)

URL = f"{API}/barbershops"


async def test_register_barbershop_stores_name(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, barbershop = await register(client, identity, "owner-1")

    assert (barbershop["name"], barbershop["first_name"]) == ("Barbearia do João", "João")
    me = await client.get(f"{URL}/me", headers=auth(token))
    assert me.json()["id"] == barbershop["id"]
    [row] = await history_rows(session_factory, Barbershop)
    assert (row["operation"], row["changed_by"]) == ("insert", "owner-1")


async def test_register_requires_token(client: AsyncClient) -> None:
    response = await client.post(URL, json=barbershop_payload())
    assert response.status_code == 401


async def test_register_requires_name(client: AsyncClient, identity: FakeIdentityProvider) -> None:
    token = identity.add_user("owner-1")
    for name in ("", "   "):
        response = await client.post(URL, json=barbershop_payload(name=name), headers=auth(token))
        assert response.status_code == 422, name
    payload = barbershop_payload()
    del payload["name"]
    assert (await client.post(URL, json=payload, headers=auth(token))).status_code == 422


async def test_register_conflicts(client: AsyncClient, identity: FakeIdentityProvider) -> None:
    token, _ = await register(client, identity, "owner-1")
    other = identity.add_user("owner-2")

    again = await client.post(URL, json=barbershop_payload(), headers=auth(token))
    same_name = await client.post(URL, json=barbershop_payload(), headers=auth(other))

    assert again.status_code == 409
    assert same_name.status_code == 201


async def test_update_barbershop(client: AsyncClient, identity: FakeIdentityProvider) -> None:
    token, _ = await register(client, identity, "owner-1")

    renamed = await client.patch(f"{URL}/me", json={"last_name": "Souza"}, headers=auth(token))
    shop = await client.patch(f"{URL}/me", json={"name": "Nova Barbearia"}, headers=auth(token))
    null = await client.patch(f"{URL}/me", json={"first_name": None}, headers=auth(token))

    assert renamed.json()["last_name"] == "Souza"
    assert shop.json()["name"] == "Nova Barbearia"
    assert null.status_code == 422


async def test_public_listing_and_details(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    _, first = await register(client, identity, "owner-1", name="Zeca Cortes")
    await register(client, identity, "owner-2", name="Ana Studio")

    listing = await client.get(URL)
    detail = await client.get(f"{URL}/{first['id']}")

    assert [item["name"] for item in listing.json()["items"]] == ["Ana Studio", "Zeca Cortes"]
    assert listing.json()["total"] == 2
    assert detail.json() == {key: first[key] for key in ("id", "name", "first_name", "last_name")}
    assert (await client.get(f"{URL}/00000000-0000-0000-0000-000000000000")).status_code == 404


async def test_unregister_purges_everything(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, barbershop = await register(client, identity, "owner-1")
    service = await create_service(client, token)
    await set_schedule(client, token)
    slot = {"starts_at": iso(at())}
    await book(client, barbershop["id"], slot, [service["id"]])

    response = await client.delete(f"{URL}/me", headers=auth(token))

    assert response.status_code == 204
    assert (await client.get(f"{URL}/me", headers=auth(token))).status_code == 404
    for model in (Service, Appointment, AppointmentItem):
        operations = [row["operation"] for row in await history_rows(session_factory, model)]
        assert operations == ["insert", "delete"], model.__name__
    shop = [row["operation"] for row in await history_rows(session_factory, Barbershop)]
    assert shop == ["insert", "delete"]
    hours = [row["operation"] for row in await history_rows(session_factory, WorkingHours)]
    assert sorted(hours) == ["delete"] * 7 + ["insert"] * 7
