from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, UnprocessableError
from app.models.barbershop import Barbershop
from app.models.base import utc_now
from app.repositories.absence import AbsenceRepository
from app.repositories.appointment import AppointmentRepository
from app.repositories.barbershop import BarbershopRepository
from app.repositories.working_hours import WorkingHoursRepository


def local_zone() -> ZoneInfo:
    return ZoneInfo(settings.time_zone)


class Availability:
    def __init__(self, session: AsyncSession) -> None:
        self.barbershops = BarbershopRepository(session)
        self.hours = WorkingHoursRepository(session)
        self.appointments = AppointmentRepository(session)
        self.absences = AbsenceRepository(session)

    async def ensure_bookable(
        self, barbershop: Barbershop, starts_at: datetime, exclude_id: UUID | None = None
    ) -> datetime:
        await self.barbershops.lock(barbershop.id)
        if starts_at <= utc_now():
            raise UnprocessableError("Time slot has already started")
        await self._ensure_within_schedule(barbershop, starts_at)
        ends_at = starts_at + timedelta(minutes=barbershop.slot_minutes)
        if await self.absences.overlaps(barbershop.id, starts_at, ends_at):
            raise UnprocessableError("Time slot is blocked by an absence")
        if await self.appointments.overlaps(barbershop.id, starts_at, ends_at, exclude_id):
            raise ConflictError("Time slot is already booked")
        return ends_at

    async def _ensure_within_schedule(self, barbershop: Barbershop, starts_at: datetime) -> None:
        local = starts_at.astimezone(local_zone())
        working = next(
            (
                item
                for item in await self.hours.for_barbershop(barbershop.id)
                if item.weekday == local.weekday()
            ),
            None,
        )
        if working is None:
            raise UnprocessableError("The barbershop is closed on this day")
        opens = working.opens_at.hour * 60 + working.opens_at.minute
        closes = working.closes_at.hour * 60 + working.closes_at.minute
        minute = local.hour * 60 + local.minute
        aligned = (
            local.second == 0
            and local.microsecond == 0
            and (minute - opens) % barbershop.slot_minutes == 0
        )
        if not aligned or minute < opens or minute + barbershop.slot_minutes > closes:
            raise UnprocessableError("Time is outside the working hours")
