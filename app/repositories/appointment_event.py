from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, func, select

from app.models.appointment import Appointment
from app.models.appointment_event import (
    AppointmentEvent,
    AppointmentEventActor,
    AppointmentEventKind,
)
from app.repositories.base import BaseRepository


class AppointmentEventRepository(BaseRepository[AppointmentEvent]):
    model = AppointmentEvent

    async def record(
        self,
        appointment: Appointment,
        kind: AppointmentEventKind,
        actor: AppointmentEventActor,
        previous_starts_at: datetime | None = None,
    ) -> AppointmentEvent:
        return await self.add(
            AppointmentEvent(
                barbershop_id=appointment.barbershop_id,
                appointment_id=appointment.id,
                kind=kind,
                actor=actor,
                starts_at=appointment.starts_at,
                previous_starts_at=previous_starts_at,
            )
        )

    async def list_for_barbershop(
        self,
        barbershop_id: UUID,
        *,
        offset: int,
        limit: int,
        appointment_id: UUID | None = None,
        created_from: datetime | None = None,
        created_until: datetime | None = None,
    ) -> tuple[Sequence[AppointmentEvent], int]:
        conditions: list[ColumnElement[bool]] = [AppointmentEvent.barbershop_id == barbershop_id]
        if appointment_id is not None:
            conditions.append(AppointmentEvent.appointment_id == appointment_id)
        if created_from is not None:
            conditions.append(AppointmentEvent.created_at >= created_from)
        if created_until is not None:
            conditions.append(AppointmentEvent.created_at < created_until)
        stmt = (
            select(AppointmentEvent)
            .where(*conditions)
            .order_by(AppointmentEvent.created_at.desc(), AppointmentEvent.id.desc())
        )
        items = (await self.session.scalars(stmt.offset(offset).limit(limit))).all()
        total = await self.session.scalar(
            select(func.count(AppointmentEvent.id)).where(*conditions)
        )
        return items, total or 0

    async def for_appointment(self, appointment_id: UUID) -> Sequence[AppointmentEvent]:
        stmt = (
            select(AppointmentEvent)
            .where(AppointmentEvent.appointment_id == appointment_id)
            .order_by(AppointmentEvent.created_at, AppointmentEvent.id)
        )
        return (await self.session.scalars(stmt)).all()
