from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import AppointmentServiceDep, CurrentUserDep
from app.api.filters import PeriodDep
from app.api.pagination import PaginationDep, to_page
from app.schemas.appointment import AppointmentCreate, AppointmentRead, AppointmentUpdate
from app.schemas.common import Page

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post("", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    data: AppointmentCreate, user: CurrentUserDep, service: AppointmentServiceDep
) -> AppointmentRead:
    return AppointmentRead.model_validate(await service.create(user, data))


@router.get("", response_model=Page[AppointmentRead])
async def list_appointments(
    user: CurrentUserDep,
    service: AppointmentServiceDep,
    pagination: PaginationDep,
    period: PeriodDep,
) -> Page[AppointmentRead]:
    result = await service.list(
        user,
        offset=pagination.offset,
        limit=pagination.limit,
        starts_from=period.starts_from,
        starts_until=period.starts_until,
    )
    return to_page(AppointmentRead, result, pagination)


@router.get("/{appointment_id}", response_model=AppointmentRead)
async def get_appointment(
    appointment_id: UUID, user: CurrentUserDep, service: AppointmentServiceDep
) -> AppointmentRead:
    return AppointmentRead.model_validate(await service.get(user, appointment_id))


@router.patch("/{appointment_id}", response_model=AppointmentRead)
async def update_appointment(
    appointment_id: UUID,
    data: AppointmentUpdate,
    user: CurrentUserDep,
    service: AppointmentServiceDep,
) -> AppointmentRead:
    return AppointmentRead.model_validate(await service.update(user, appointment_id, data))


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_appointment(
    appointment_id: UUID, user: CurrentUserDep, service: AppointmentServiceDep
) -> None:
    await service.delete(user, appointment_id)
