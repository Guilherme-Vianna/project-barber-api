from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser
from app.core.exceptions import ConflictError, NotFoundError
from app.models.barbershop import Barbershop
from app.repositories.absence import AbsenceRepository
from app.repositories.appointment import AppointmentItemRepository, AppointmentRepository
from app.repositories.appointment_event import AppointmentEventRepository
from app.repositories.barbershop import BarbershopRepository
from app.repositories.service import ServiceRepository
from app.repositories.working_hours import WorkingHoursRepository
from app.schemas.barbershop import BarbershopCreate, BarbershopUpdate
from app.services.common import existing_barbershop


class BarbershopService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.barbershops = BarbershopRepository(session)

    async def list(self, *, offset: int, limit: int) -> tuple[Sequence[Barbershop], int]:
        return await self.barbershops.list_sorted(offset=offset, limit=limit)

    async def get(self, barbershop_id: UUID) -> Barbershop:
        return await existing_barbershop(self.barbershops, barbershop_id)

    async def get_for_user(self, user: AuthenticatedUser) -> Barbershop:
        barbershop = await self.barbershops.get_by_firebase_uid(user.uid)
        if barbershop is None:
            raise NotFoundError("Current user has no registered barbershop")
        return barbershop

    async def register(self, user: AuthenticatedUser, data: BarbershopCreate) -> Barbershop:
        await self.barbershops.lock_uid(user.uid)
        if await self.barbershops.get_by_firebase_uid(user.uid) is not None:
            raise ConflictError("User already has a registered barbershop")
        return await self._persist(
            self.barbershops.add(Barbershop(firebase_uid=user.uid, **data.model_dump()))
        )

    async def update(self, user: AuthenticatedUser, data: BarbershopUpdate) -> Barbershop:
        barbershop = await self.get_for_user(user)
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(barbershop, field, value)
        return await self._persist(self.barbershops.save(barbershop))

    async def unregister(self, user: AuthenticatedUser) -> None:
        barbershop = await self.get_for_user(user)
        appointments = AppointmentRepository(self.session)
        items = AppointmentItemRepository(self.session)
        for appointment in await appointments.find_for_barbershop(barbershop.id):
            for item in await items.find_by(appointment_id=appointment.id):
                await items.delete(item)
            await appointments.delete(appointment)
        events = AppointmentEventRepository(self.session)
        for event in await events.find_by(barbershop_id=barbershop.id):
            await events.delete(event)
        absences = AbsenceRepository(self.session)
        for absence in await absences.find_by(barbershop_id=barbershop.id):
            await absences.delete(absence)
        hours = WorkingHoursRepository(self.session)
        for item in await hours.find_by(barbershop_id=barbershop.id):
            await hours.delete(item)
        services = ServiceRepository(self.session)
        for service in await services.find_by(barbershop_id=barbershop.id):
            await services.delete(service)
        await self.barbershops.delete(barbershop)
        await self.session.commit()

    async def _persist(self, operation) -> Barbershop:
        try:
            barbershop = await operation
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("User already has a registered barbershop") from exc
        return barbershop
