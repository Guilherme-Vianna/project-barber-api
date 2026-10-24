import hashlib
from collections.abc import Iterable, Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser
from app.core.cache import cache_until
from app.core.exceptions import ConflictError, NotFoundError, UnprocessableError
from app.models.appointment import Appointment, AppointmentItem
from app.models.appointment_event import (
    AppointmentEvent,
    AppointmentEventActor,
    AppointmentEventKind,
)
from app.models.barbershop import Barbershop
from app.models.base import utc_now
from app.models.service import Service
from app.repositories.appointment import AppointmentItemRepository, AppointmentRepository
from app.repositories.appointment_event import AppointmentEventRepository
from app.repositories.barbershop import BarbershopRepository
from app.repositories.service import ServiceRepository
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentRead,
    AppointmentUpdate,
    BookingRead,
    BookingReschedule,
)
from app.services.availability import Availability
from app.services.common import existing_barbershop, require_barbershop

OWNER = AppointmentEventActor.OWNER
CUSTOMER = AppointmentEventActor.CUSTOMER


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def cancel_appointment(
    appointment: Appointment,
    actor: AppointmentEventActor,
    appointments: AppointmentRepository,
    items: AppointmentItemRepository,
    events: AppointmentEventRepository,
) -> None:
    await events.record(appointment, AppointmentEventKind.CANCELLED, actor)
    for item in await items.find_by(appointment_id=appointment.id):
        await items.delete(item)
    await appointments.delete(appointment)


class AppointmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.barbershops = BarbershopRepository(session)
        self.availability = Availability(session)
        self.services = ServiceRepository(session)
        self.appointments = AppointmentRepository(session)
        self.items = AppointmentItemRepository(session)
        self.events = AppointmentEventRepository(session)

    async def book(
        self, barbershop_id: UUID, data: AppointmentCreate, customer_token: str
    ) -> Appointment:
        barbershop = await existing_barbershop(self.barbershops, barbershop_id)
        token_hash = hash_token(customer_token)
        await self.barbershops.lock(barbershop.id)
        if await self.appointments.upcoming_for_customer(barbershop.id, token_hash, utc_now()):
            raise ConflictError("Customer already has an upcoming appointment")
        return await self._create(barbershop, data, CUSTOMER, token_hash)

    async def create(self, user: AuthenticatedUser, data: AppointmentCreate) -> Appointment:
        barbershop = await require_barbershop(self.barbershops, user)
        return await self._create(barbershop, data, OWNER)

    async def my_booking(self, barbershop_id: UUID, customer_token: str) -> BookingRead:
        barbershop = await existing_barbershop(self.barbershops, barbershop_id)
        appointment = await self._mine(barbershop, customer_token)
        cache_until(appointment.starts_at)
        return self._booking(barbershop, appointment)

    async def my_booking_events(
        self, barbershop_id: UUID, customer_token: str
    ) -> Sequence[AppointmentEvent]:
        barbershop = await existing_barbershop(self.barbershops, barbershop_id)
        appointment = await self._mine(barbershop, customer_token)
        cache_until(appointment.starts_at)
        return await self.events.for_appointment(appointment.id)

    async def reschedule_my_booking(
        self, barbershop_id: UUID, customer_token: str, data: BookingReschedule
    ) -> BookingRead:
        barbershop = await existing_barbershop(self.barbershops, barbershop_id)
        appointment = await self._mine(barbershop, customer_token)
        await self._move(barbershop, appointment, data.starts_at, CUSTOMER)
        await self._commit()
        return self._booking(barbershop, await self._owned(barbershop, appointment.id))

    async def cancel_my_booking(self, barbershop_id: UUID, customer_token: str) -> None:
        barbershop = await existing_barbershop(self.barbershops, barbershop_id)
        appointment = await self._mine(barbershop, customer_token)
        await cancel_appointment(appointment, CUSTOMER, self.appointments, self.items, self.events)
        await self.session.commit()

    @staticmethod
    def _booking(barbershop: Barbershop, appointment: Appointment) -> BookingRead:
        return BookingRead.model_validate(
            {
                **AppointmentRead.model_validate(appointment).model_dump(),
                "barbershop_id": barbershop.id,
                "barbershop_name": barbershop.name,
            }
        )

    async def list_public(
        self,
        barbershop_id: UUID,
        *,
        offset: int,
        limit: int,
        starts_from: datetime | None,
        starts_until: datetime | None,
    ) -> tuple[Sequence[Appointment], int]:
        await existing_barbershop(self.barbershops, barbershop_id)
        return await self.appointments.list_for_barbershop(
            barbershop_id,
            offset=offset,
            limit=limit,
            starts_from=starts_from,
            starts_until=starts_until,
            with_items=False,
        )

    async def list(
        self,
        user: AuthenticatedUser,
        *,
        offset: int,
        limit: int,
        starts_from: datetime | None,
        starts_until: datetime | None,
    ) -> tuple[Sequence[Appointment], int]:
        barbershop = await require_barbershop(self.barbershops, user)
        return await self.appointments.list_for_barbershop(
            barbershop.id,
            offset=offset,
            limit=limit,
            starts_from=starts_from,
            starts_until=starts_until,
        )

    async def list_events(
        self,
        user: AuthenticatedUser,
        *,
        offset: int,
        limit: int,
        appointment_id: UUID | None,
        created_from: datetime | None,
        created_until: datetime | None,
    ) -> tuple[Sequence[AppointmentEvent], int]:
        barbershop = await require_barbershop(self.barbershops, user)
        return await self.events.list_for_barbershop(
            barbershop.id,
            offset=offset,
            limit=limit,
            appointment_id=appointment_id,
            created_from=created_from,
            created_until=created_until,
        )

    async def get(self, user: AuthenticatedUser, appointment_id: UUID) -> Appointment:
        barbershop = await require_barbershop(self.barbershops, user)
        return await self._owned(barbershop, appointment_id)

    async def update(
        self, user: AuthenticatedUser, appointment_id: UUID, data: AppointmentUpdate
    ) -> Appointment:
        barbershop = await require_barbershop(self.barbershops, user)
        appointment = await self._owned(barbershop, appointment_id)
        changes = data.model_dump(exclude_unset=True)
        starts_at = changes.pop("starts_at", appointment.starts_at)
        service_ids = changes.pop("service_ids", None)
        current_services = {item.service_id for item in appointment.items}
        updated = any(getattr(appointment, field) != value for field, value in changes.items())
        updated |= service_ids is not None and set(service_ids) != current_services
        for field, value in changes.items():
            setattr(appointment, field, value)
        try:
            if starts_at != appointment.starts_at:
                await self._move(barbershop, appointment, starts_at, OWNER)
            else:
                await self.appointments.save(appointment)
            if service_ids is not None:
                await self._sync_items(barbershop, appointment, service_ids)
            if updated:
                await self.events.record(appointment, AppointmentEventKind.UPDATED, OWNER)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Time slot is already booked") from exc
        return await self._owned(barbershop, appointment.id)

    async def delete(self, user: AuthenticatedUser, appointment_id: UUID) -> None:
        barbershop = await require_barbershop(self.barbershops, user)
        appointment = await self._owned(barbershop, appointment_id)
        await cancel_appointment(appointment, OWNER, self.appointments, self.items, self.events)
        await self.session.commit()

    async def _create(
        self,
        barbershop: Barbershop,
        data: AppointmentCreate,
        actor: AppointmentEventActor,
        customer_token_hash: str | None = None,
    ) -> Appointment:
        ends_at = await self.availability.ensure_bookable(barbershop, data.starts_at)
        services = await self._bookable_services(barbershop, data.service_ids)
        try:
            appointment = await self.appointments.add(
                Appointment(
                    barbershop_id=barbershop.id,
                    ends_at=ends_at,
                    customer_token_hash=customer_token_hash,
                    **data.model_dump(exclude={"service_ids"}),
                )
            )
            for service in services:
                await self.items.add(self._item(appointment, service))
            await self.events.record(appointment, AppointmentEventKind.BOOKED, actor)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Time slot is already booked") from exc
        return await self._owned(barbershop, appointment.id)

    async def _move(
        self,
        barbershop: Barbershop,
        appointment: Appointment,
        starts_at: datetime,
        actor: AppointmentEventActor,
    ) -> None:
        if starts_at == appointment.starts_at:
            return
        ends_at = await self.availability.ensure_bookable(
            barbershop, starts_at, exclude_id=appointment.id
        )
        previous = appointment.starts_at
        appointment.starts_at = starts_at
        appointment.ends_at = ends_at
        await self.appointments.save(appointment)
        await self.events.record(
            appointment, AppointmentEventKind.RESCHEDULED, actor, previous_starts_at=previous
        )

    async def _commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Time slot is already booked") from exc

    async def _mine(self, barbershop: Barbershop, customer_token: str) -> Appointment:
        found = await self.appointments.upcoming_for_customer(
            barbershop.id, hash_token(customer_token), utc_now()
        )
        if found is None:
            raise NotFoundError("No upcoming booking")
        appointment = await self._owned(barbershop, found.id)
        return appointment

    async def _sync_items(
        self, barbershop: Barbershop, appointment: Appointment, service_ids: list[UUID]
    ) -> None:
        current = {item.service_id: item for item in appointment.items}
        for service_id, item in current.items():
            if service_id not in service_ids:
                await self.items.delete(item)
        added = [service_id for service_id in service_ids if service_id not in current]
        for service in await self._bookable_services(barbershop, added):
            await self.items.add(self._item(appointment, service))

    async def _owned(self, barbershop: Barbershop, appointment_id: UUID) -> Appointment:
        appointment = await self.appointments.get_aggregate(appointment_id, barbershop.id)
        if appointment is None:
            raise NotFoundError(f"Appointment {appointment_id} not found")
        return appointment

    async def _bookable_services(
        self, barbershop: Barbershop, service_ids: Iterable[UUID]
    ) -> list[Service]:
        ids = list(service_ids)
        found = await self.services.find_for_barbershop(barbershop.id, ids)
        unavailable = [
            str(service_id)
            for service_id in ids
            if service_id not in found or not found[service_id].active
        ]
        if unavailable:
            raise UnprocessableError(f"Services are not available: {', '.join(unavailable)}")
        return [found[service_id] for service_id in ids]

    @staticmethod
    def _item(appointment: Appointment, service: Service) -> AppointmentItem:
        return AppointmentItem(
            appointment_id=appointment.id, service_id=service.id, price=service.price
        )
