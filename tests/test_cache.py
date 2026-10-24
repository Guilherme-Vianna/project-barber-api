import time

import pytest
from httpx import AsyncClient

from app.api.cache import token_expiry
from app.core.config import settings
from app.integrations.redis import get_response_cache
from app.main import app
from tests.fakes import FakeIdentityProvider, FakeResponseCache, fake_token
from tests.helpers import (
    API,
    at,
    auth,
    book,
    create_service,
    register,
    slot_at,
    window,
)

SERVICES_URL = f"{API}/services"


async def test_repeated_reads_are_served_from_cache(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, _ = await register(client, identity, "owner-1")
    await create_service(client, token)

    first = await client.get(SERVICES_URL, headers=auth(token))
    second = await client.get(SERVICES_URL, headers=auth(token))

    assert "x-cache" not in first.headers
    assert second.headers["x-cache"] == "HIT"
    assert second.json() == first.json()


async def test_public_reads_are_cached(
    client: AsyncClient, identity: FakeIdentityProvider, cache: FakeResponseCache
) -> None:
    token, barbershop = await register(client, identity, "owner-1")
    await create_service(client, token)
    url = f"{API}/barbershops/{barbershop['id']}/services"

    await client.get(url)
    second = await client.get(url)

    assert second.headers["x-cache"] == "HIT"
    assert list(cache.ttls.values()) == [600]


async def test_writes_invalidate_cached_reads(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, barbershop = await register(client, identity, "owner-1")
    await create_service(client, token, "Haircut")
    url = f"{API}/barbershops/{barbershop['id']}/services"
    await client.get(url)
    await client.get(SERVICES_URL, headers=auth(token))

    await create_service(client, token, "Beard")
    public = await client.get(url)
    owner = await client.get(SERVICES_URL, headers=auth(token))

    for response in (public, owner):
        assert "x-cache" not in response.headers
        assert [item["name"] for item in response.json()["items"]] == ["Beard", "Haircut"]


async def test_public_booking_invalidates_owner_reads(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, barbershop = await register(client, identity, "owner-1")
    service = await create_service(client, token)
    slot = await slot_at(client, token, at())
    slots_url = f"{API}/barbershops/{barbershop['id']}/appointments"
    await client.get(f"{API}/appointments", headers=auth(token))
    await client.get(slots_url, params=window())

    await book(client, barbershop["id"], slot, [service["id"]])
    appointments = await client.get(f"{API}/appointments", headers=auth(token))
    public_slots = await client.get(slots_url, params=window())

    assert appointments.json()["total"] == 1
    assert public_slots.json()["total"] == 1


async def test_cache_is_scoped_by_token_and_query(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    first_token, _ = await register(client, identity, "owner-1")
    second_token, _ = await register(client, identity, "owner-2")
    await create_service(client, first_token)
    await client.get(SERVICES_URL, headers=auth(first_token))

    other_user = await client.get(SERVICES_URL, headers=auth(second_token))
    other_query = await client.get(f"{SERVICES_URL}?limit=1", headers=auth(first_token))
    anonymous = await client.get(SERVICES_URL)

    assert "x-cache" not in other_user.headers
    assert other_user.json()["items"] == []
    assert "x-cache" not in other_query.headers
    assert anonymous.status_code == 401


async def test_errors_are_not_cached(client: AsyncClient, identity: FakeIdentityProvider) -> None:
    token = identity.add_user("someone")

    await client.get(SERVICES_URL, headers=auth(token))
    response = await client.get(SERVICES_URL, headers=auth(token))

    assert response.status_code == 403
    assert "x-cache" not in response.headers


async def test_entries_expire_with_tokens(
    client: AsyncClient, identity: FakeIdentityProvider, cache: FakeResponseCache
) -> None:
    await register(client, identity, "owner-1")
    token = fake_token("owner-1", time.time() + 60)
    identity.tokens[token] = "owner-1"

    await client.get(SERVICES_URL, headers=auth(token))

    [ttl] = cache.ttls.values()
    assert 0 < ttl <= 60


async def test_requests_work_when_cache_is_unavailable(
    client: AsyncClient, identity: FakeIdentityProvider, cache: FakeResponseCache
) -> None:
    token, _ = await register(client, identity, "owner-1")
    cache.available = False
    await create_service(client, token)

    first = await client.get(SERVICES_URL, headers=auth(token))
    second = await client.get(SERVICES_URL, headers=auth(token))

    assert first.status_code == second.status_code == 200
    assert "x-cache" not in second.headers
    assert cache.entries == {}


async def test_lost_versions_invalidate_every_entry(
    client: AsyncClient, identity: FakeIdentityProvider, cache: FakeResponseCache
) -> None:
    token, _ = await register(client, identity, "owner-1")
    await client.get(SERVICES_URL, headers=auth(token))

    cache.versions.clear()
    response = await client.get(SERVICES_URL, headers=auth(token))

    assert "x-cache" not in response.headers


def test_cache_is_disabled_without_redis_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "redis_url", None)
    get_response_cache.cache_clear()
    try:
        assert get_response_cache() is None
    finally:
        get_response_cache.cache_clear()


async def test_api_works_without_cache(client: AsyncClient, identity: FakeIdentityProvider) -> None:
    app.dependency_overrides[get_response_cache] = lambda: None
    token, barbershop = await register(client, identity, "owner-1")
    service = await create_service(client, token)
    slot = await slot_at(client, token, at())

    for _ in range(2):
        owner = await client.get(SERVICES_URL, headers=auth(token))
        public = await client.get(
            f"{API}/barbershops/{barbershop['id']}/appointments", params=window()
        )
        assert owner.status_code == public.status_code == 200
        assert "x-cache" not in owner.headers
        assert "x-cache" not in public.headers
    await book(client, barbershop["id"], slot, [service["id"]])
    after = await client.get(f"{API}/barbershops/{barbershop['id']}/appointments", params=window())
    assert after.json()["total"] == 1


def test_token_expiry_is_read_from_the_payload() -> None:
    expires_at = time.time() + 60

    assert token_expiry(fake_token("user-1", expires_at)) == expires_at
    assert token_expiry("not-a-jwt") is None
