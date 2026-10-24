from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import AbsenceServiceDep, CurrentUserDep
from app.api.filters import PeriodDep
from app.api.pagination import PaginationDep, to_page
from app.schemas.absence import AbsenceCreate, AbsenceCreated, AbsenceRead
from app.schemas.common import Page

router = APIRouter(prefix="/absences", tags=["absences"])


@router.post("", response_model=AbsenceCreated, status_code=status.HTTP_201_CREATED)
async def create_absence(
    data: AbsenceCreate, user: CurrentUserDep, service: AbsenceServiceDep
) -> AbsenceCreated:
    return await service.create(user, data)


@router.get("", response_model=Page[AbsenceRead])
async def list_absences(
    user: CurrentUserDep,
    service: AbsenceServiceDep,
    pagination: PaginationDep,
    period: PeriodDep,
) -> Page[AbsenceRead]:
    result = await service.list(
        user,
        offset=pagination.offset,
        limit=pagination.limit,
        starts_from=period.starts_from,
        starts_until=period.starts_until,
    )
    return to_page(AbsenceRead, result, pagination)


@router.delete("/{absence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_absence(
    absence_id: UUID, user: CurrentUserDep, service: AbsenceServiceDep
) -> None:
    await service.delete(user, absence_id)
