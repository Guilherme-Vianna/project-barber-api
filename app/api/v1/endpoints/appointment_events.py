from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import AwareDatetime

from app.api.deps import AppointmentServiceDep, CurrentUserDep
from app.api.pagination import PaginationDep, to_page
from app.core.exceptions import UnprocessableError
from app.schemas.appointment import AppointmentEventRead
from app.schemas.common import Page

router = APIRouter(prefix="/appointment-events", tags=["appointment events"])


@router.get("", response_model=Page[AppointmentEventRead])
async def list_appointment_events(
    user: CurrentUserDep,
    service: AppointmentServiceDep,
    pagination: PaginationDep,
    appointment_id: UUID | None = None,
    created_from: Annotated[AwareDatetime | None, Query(alias="from")] = None,
    created_until: Annotated[AwareDatetime | None, Query(alias="to")] = None,
) -> Page[AppointmentEventRead]:
    if created_from and created_until and created_until <= created_from:
        raise UnprocessableError("'to' must be after 'from'")
    result = await service.list_events(
        user,
        offset=pagination.offset,
        limit=pagination.limit,
        appointment_id=appointment_id,
        created_from=created_from,
        created_until=created_until,
    )
    return to_page(AppointmentEventRead, result, pagination)
