from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser
from app.core.exceptions import ConflictError
from app.models.barbershop import Barbershop
from app.models.working_hours import WorkingHours
from app.repositories.barbershop import BarbershopRepository
from app.repositories.working_hours import WorkingHoursRepository
from app.schemas.schedule import ScheduleRead, ScheduleUpdate
from app.services.common import existing_barbershop, require_barbershop


class ScheduleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.barbershops = BarbershopRepository(session)
        self.hours = WorkingHoursRepository(session)

    async def get(self, user: AuthenticatedUser) -> ScheduleRead:
        return await self._read(await require_barbershop(self.barbershops, user))

    async def get_public(self, barbershop_id: UUID) -> ScheduleRead:
        return await self._read(await existing_barbershop(self.barbershops, barbershop_id))

    async def replace(self, user: AuthenticatedUser, data: ScheduleUpdate) -> ScheduleRead:
        barbershop = await require_barbershop(self.barbershops, user)
        await self.barbershops.lock(barbershop.id)
        current = {item.weekday: item for item in await self.hours.for_barbershop(barbershop.id)}
        wanted = {day.weekday: day for day in data.days}
        try:
            for weekday, item in current.items():
                if weekday not in wanted:
                    await self.hours.delete(item)
            for weekday, day in wanted.items():
                item = current.get(weekday)
                if item is None:
                    await self.hours.add(
                        WorkingHours(barbershop_id=barbershop.id, **day.model_dump())
                    )
                else:
                    item.opens_at = day.opens_at
                    item.closes_at = day.closes_at
            barbershop.slot_minutes = data.slot_minutes
            await self.barbershops.save(barbershop)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Schedule could not be saved") from exc
        return await self._read(barbershop)

    async def _read(self, barbershop: Barbershop) -> ScheduleRead:
        days = await self.hours.for_barbershop(barbershop.id)
        return ScheduleRead.model_validate(
            {
                "slot_minutes": barbershop.slot_minutes,
                "days": days,
            }
        )
