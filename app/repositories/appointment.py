from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.base import ExecutableOption

from app.models.appointment import Appointment, AppointmentItem
from app.repositories.base import BaseRepository


def appointment_aggregate_options() -> list[ExecutableOption]:
    return [selectinload(Appointment.items).selectinload(AppointmentItem.service)]


class AppointmentRepository(BaseRepository[Appointment]):
    model = Appointment

    async def get_aggregate(
        self, appointment_id: UUID, barbershop_id: UUID | None = None
    ) -> Appointment | None:
        stmt = (
            select(Appointment)
            .where(Appointment.id == appointment_id)
            .options(*appointment_aggregate_options())
            .execution_options(populate_existing=True)
        )
        if barbershop_id is not None:
            stmt = stmt.where(Appointment.barbershop_id == barbershop_id)
        return await self.session.scalar(stmt)

    async def upcoming_for_customer(
        self, barbershop_id: UUID, token_hash: str, now: datetime
    ) -> Appointment | None:
        stmt = (
            select(Appointment)
            .where(
                Appointment.barbershop_id == barbershop_id,
                Appointment.customer_token_hash == token_hash,
                Appointment.starts_at > now,
            )
            .order_by(Appointment.starts_at)
            .limit(1)
            .options(*appointment_aggregate_options())
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def list_for_barbershop(
        self,
        barbershop_id: UUID,
        *,
        offset: int,
        limit: int,
        starts_from: datetime | None = None,
        starts_until: datetime | None = None,
        with_items: bool = True,
    ) -> tuple[Sequence[Appointment], int]:
        conditions = self._conditions(barbershop_id, starts_from, starts_until)
        stmt = select(Appointment).where(*conditions).order_by(Appointment.starts_at)
        if with_items:
            stmt = stmt.options(*appointment_aggregate_options())
        items = (await self.session.scalars(stmt.offset(offset).limit(limit))).all()
        total = await self.session.scalar(select(func.count(Appointment.id)).where(*conditions))
        return items, total or 0

    async def overlapping(
        self, barbershop_id: UUID, starts_at: datetime, ends_at: datetime
    ) -> Sequence[Appointment]:
        stmt = select(Appointment).where(
            Appointment.barbershop_id == barbershop_id,
            Appointment.starts_at < ends_at,
            Appointment.ends_at > starts_at,
        )
        return (await self.session.scalars(stmt)).all()

    async def overlaps(
        self,
        barbershop_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
        exclude_id: UUID | None = None,
    ) -> bool:
        conditions = [
            Appointment.barbershop_id == barbershop_id,
            Appointment.starts_at < ends_at,
            Appointment.ends_at > starts_at,
        ]
        if exclude_id is not None:
            conditions.append(Appointment.id != exclude_id)
        stmt = select(select(Appointment.id).where(*conditions).exists())
        return bool(await self.session.scalar(stmt))

    async def find_for_barbershop(self, barbershop_id: UUID) -> Sequence[Appointment]:
        return await self.find_by(barbershop_id=barbershop_id)

    @staticmethod
    def _conditions(
        barbershop_id: UUID, starts_from: datetime | None, starts_until: datetime | None
    ) -> list[ColumnElement[bool]]:
        conditions = [Appointment.barbershop_id == barbershop_id]
        if starts_from is not None:
            conditions.append(Appointment.starts_at >= starts_from)
        if starts_until is not None:
            conditions.append(Appointment.starts_at < starts_until)
        return conditions


class AppointmentItemRepository(BaseRepository[AppointmentItem]):
    model = AppointmentItem

    async def is_service_used(self, service_id: UUID) -> bool:
        used = select(AppointmentItem.id).where(AppointmentItem.service_id == service_id)
        return bool(await self.session.scalar(select(used.exists())))
