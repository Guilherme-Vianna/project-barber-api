from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser
from app.core.exceptions import NotFoundError, UnprocessableError
from app.models.absence import Absence
from app.models.appointment_event import AppointmentEventActor
from app.models.base import utc_now
from app.repositories.absence import AbsenceRepository
from app.repositories.appointment import AppointmentItemRepository, AppointmentRepository
from app.repositories.appointment_event import AppointmentEventRepository
from app.repositories.barbershop import BarbershopRepository
from app.schemas.absence import AbsenceCreate, AbsenceCreated, AbsenceRead
from app.services.appointment import cancel_appointment
from app.services.common import existing_barbershop, require_barbershop


class AbsenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.barbershops = BarbershopRepository(session)
        self.absences = AbsenceRepository(session)
        self.appointments = AppointmentRepository(session)
        self.items = AppointmentItemRepository(session)
        self.events = AppointmentEventRepository(session)

    async def create(self, user: AuthenticatedUser, data: AbsenceCreate) -> AbsenceCreated:
        barbershop = await require_barbershop(self.barbershops, user)
        if data.ends_at <= utc_now():
            raise UnprocessableError("The absence must end in the future")
        await self.barbershops.lock(barbershop.id)
        affected = await self.appointments.overlapping(barbershop.id, data.starts_at, data.ends_at)
        for appointment in affected:
            await cancel_appointment(
                appointment,
                AppointmentEventActor.ABSENCE,
                self.appointments,
                self.items,
                self.events,
            )
        absence = await self.absences.add(Absence(barbershop_id=barbershop.id, **data.model_dump()))
        await self.session.commit()
        read = AbsenceRead.model_validate(absence)
        return AbsenceCreated(**read.model_dump(), cancelled_appointments=len(affected))

    async def list(
        self,
        user: AuthenticatedUser,
        *,
        offset: int,
        limit: int,
        starts_from: datetime | None,
        starts_until: datetime | None,
    ) -> tuple[Sequence[Absence], int]:
        barbershop = await require_barbershop(self.barbershops, user)
        return await self.absences.list_for_barbershop(
            barbershop.id,
            offset=offset,
            limit=limit,
            starts_from=starts_from,
            starts_until=starts_until,
        )

    async def list_public(
        self,
        barbershop_id: UUID,
        *,
        offset: int,
        limit: int,
        starts_from: datetime | None,
        starts_until: datetime | None,
    ) -> tuple[Sequence[Absence], int]:
        await existing_barbershop(self.barbershops, barbershop_id)
        return await self.absences.list_for_barbershop(
            barbershop_id,
            offset=offset,
            limit=limit,
            starts_from=starts_from,
            starts_until=starts_until,
        )

    async def delete(self, user: AuthenticatedUser, absence_id: UUID) -> None:
        barbershop = await require_barbershop(self.barbershops, user)
        absence = await self.absences.get_owned(barbershop.id, absence_id)
        if absence is None:
            raise NotFoundError(f"Absence {absence_id} not found")
        await self.absences.delete(absence)
        await self.session.commit()
