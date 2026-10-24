from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import CatalogServiceDep, CurrentUserDep
from app.api.pagination import PaginationDep, to_page
from app.schemas.common import Page
from app.schemas.service import ServiceCreate, ServiceRead, ServiceUpdate

router = APIRouter(prefix="/services", tags=["services"])


@router.post("", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
async def create_service(
    data: ServiceCreate, user: CurrentUserDep, service: CatalogServiceDep
) -> ServiceRead:
    return ServiceRead.model_validate(await service.create(user, data))


@router.get("", response_model=Page[ServiceRead])
async def list_services(
    user: CurrentUserDep,
    service: CatalogServiceDep,
    pagination: PaginationDep,
    search: Annotated[str | None, Query(max_length=100)] = None,
    active: bool | None = None,
) -> Page[ServiceRead]:
    result = await service.list(
        user, offset=pagination.offset, limit=pagination.limit, search=search, active=active
    )
    return to_page(ServiceRead, result, pagination)


@router.get("/{service_id}", response_model=ServiceRead)
async def get_service(
    service_id: UUID, user: CurrentUserDep, service: CatalogServiceDep
) -> ServiceRead:
    return ServiceRead.model_validate(await service.get(user, service_id))


@router.patch("/{service_id}", response_model=ServiceRead)
async def update_service(
    service_id: UUID, data: ServiceUpdate, user: CurrentUserDep, service: CatalogServiceDep
) -> ServiceRead:
    return ServiceRead.model_validate(await service.update(user, service_id, data))


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    service_id: UUID, user: CurrentUserDep, service: CatalogServiceDep
) -> None:
    await service.delete(user, service_id)
