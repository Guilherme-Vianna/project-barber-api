from fastapi import APIRouter

from app.api.deps import CurrentUserDep, ScheduleServiceDep
from app.schemas.schedule import ScheduleRead, ScheduleUpdate

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.get("", response_model=ScheduleRead)
async def get_schedule(user: CurrentUserDep, service: ScheduleServiceDep) -> ScheduleRead:
    return await service.get(user)


@router.put("", response_model=ScheduleRead)
async def replace_schedule(
    data: ScheduleUpdate, user: CurrentUserDep, service: ScheduleServiceDep
) -> ScheduleRead:
    return await service.replace(user, data)
