from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import (
    BarbershopServiceDep,
    CurrentUserDep,
    CustomerTokenDep,
    PublicAbsenceServiceDep,
    PublicAppointmentServiceDep,
    PublicBarbershopServiceDep,
    PublicCatalogServiceDep,
    PublicScheduleServiceDep,
)
from app.api.filters import PeriodDep
from app.api.pagination import PaginationDep, to_page
from app.schemas.absence import AbsencePublicRead
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentEventPublicRead,
    AppointmentPublicRead,
    AppointmentRead,
    BookingRead,
    BookingReschedule,
)
from app.schemas.barbershop import (
    BarbershopCreate,
    BarbershopPublicRead,
    BarbershopRead,
    BarbershopUpdate,
)
from app.schemas.common import Page
from app.schemas.schedule import ScheduleRead
from app.schemas.service import ServicePublicRead

router = APIRouter(prefix="/barbershops", tags=["barbershops"])


@router.post("", response_model=BarbershopRead, status_code=status.HTTP_201_CREATED)
async def register_barbershop(
    data: BarbershopCreate, user: CurrentUserDep, service: BarbershopServiceDep
) -> BarbershopRead:
    return BarbershopRead.model_validate(await service.register(user, data))


@router.get("", response_model=Page[BarbershopPublicRead])
async def list_barbershops(
    service: PublicBarbershopServiceDep, pagination: PaginationDep
) -> Page[BarbershopPublicRead]:
    result = await service.list(offset=pagination.offset, limit=pagination.limit)
    return to_page(BarbershopPublicRead, result, pagination)


@router.get("/me", response_model=BarbershopRead)
async def get_my_barbershop(user: CurrentUserDep, service: BarbershopServiceDep) -> BarbershopRead:
    return BarbershopRead.model_validate(await service.get_for_user(user))


@router.patch("/me", response_model=BarbershopRead)
async def update_my_barbershop(
    data: BarbershopUpdate, user: CurrentUserDep, service: BarbershopServiceDep
) -> BarbershopRead:
    return BarbershopRead.model_validate(await service.update(user, data))


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_barbershop(user: CurrentUserDep, service: BarbershopServiceDep) -> None:
    await service.unregister(user)


@router.get("/{barbershop_id}", response_model=BarbershopPublicRead)
async def get_barbershop(
    barbershop_id: UUID, service: PublicBarbershopServiceDep
) -> BarbershopPublicRead:
    return BarbershopPublicRead.model_validate(await service.get(barbershop_id))


@router.get("/{barbershop_id}/services", response_model=Page[ServicePublicRead])
async def list_barbershop_services(
    barbershop_id: UUID, service: PublicCatalogServiceDep, pagination: PaginationDep
) -> Page[ServicePublicRead]:
    result = await service.list_public(
        barbershop_id, offset=pagination.offset, limit=pagination.limit
    )
    return to_page(ServicePublicRead, result, pagination)


@router.get("/{barbershop_id}/schedule", response_model=ScheduleRead)
async def get_barbershop_schedule(
    barbershop_id: UUID, service: PublicScheduleServiceDep
) -> ScheduleRead:
    return await service.get_public(barbershop_id)


@router.get("/{barbershop_id}/appointments", response_model=Page[AppointmentPublicRead])
async def list_booked_times(
    barbershop_id: UUID,
    service: PublicAppointmentServiceDep,
    pagination: PaginationDep,
    period: PeriodDep,
) -> Page[AppointmentPublicRead]:
    result = await service.list_public(
        barbershop_id,
        offset=pagination.offset,
        limit=pagination.limit,
        starts_from=period.starts_from,
        starts_until=period.starts_until,
    )
    return to_page(AppointmentPublicRead, result, pagination)


@router.get("/{barbershop_id}/absences", response_model=Page[AbsencePublicRead])
async def list_absences(
    barbershop_id: UUID,
    service: PublicAbsenceServiceDep,
    pagination: PaginationDep,
    period: PeriodDep,
) -> Page[AbsencePublicRead]:
    result = await service.list_public(
        barbershop_id,
        offset=pagination.offset,
        limit=pagination.limit,
        starts_from=period.starts_from,
        starts_until=period.starts_until,
    )
    return to_page(AbsencePublicRead, result, pagination)


@router.post(
    "/{barbershop_id}/appointments",
    response_model=AppointmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def book_appointment(
    barbershop_id: UUID,
    data: AppointmentCreate,
    customer_token: CustomerTokenDep,
    service: PublicAppointmentServiceDep,
) -> AppointmentRead:
    return AppointmentRead.model_validate(await service.book(barbershop_id, data, customer_token))


@router.get("/{barbershop_id}/my-booking", response_model=BookingRead)
async def get_my_booking(
    barbershop_id: UUID, customer_token: CustomerTokenDep, service: PublicAppointmentServiceDep
) -> BookingRead:
    return await service.my_booking(barbershop_id, customer_token)


@router.patch("/{barbershop_id}/my-booking", response_model=BookingRead)
async def reschedule_my_booking(
    barbershop_id: UUID,
    data: BookingReschedule,
    customer_token: CustomerTokenDep,
    service: PublicAppointmentServiceDep,
) -> BookingRead:
    return await service.reschedule_my_booking(barbershop_id, customer_token, data)


@router.delete("/{barbershop_id}/my-booking", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_my_booking(
    barbershop_id: UUID, customer_token: CustomerTokenDep, service: PublicAppointmentServiceDep
) -> None:
    await service.cancel_my_booking(barbershop_id, customer_token)


@router.get("/{barbershop_id}/my-booking/events", response_model=list[AppointmentEventPublicRead])
async def list_my_booking_events(
    barbershop_id: UUID, customer_token: CustomerTokenDep, service: PublicAppointmentServiceDep
) -> list[AppointmentEventPublicRead]:
    events = await service.my_booking_events(barbershop_id, customer_token)
    return [AppointmentEventPublicRead.model_validate(event) for event in events]
