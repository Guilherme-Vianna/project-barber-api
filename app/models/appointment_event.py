from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDv7PrimaryKeyMixin, enum_check, string_enum
from app.models.history import versioned


class AppointmentEventKind(StrEnum):
    BOOKED = "booked"
    RESCHEDULED = "rescheduled"
    UPDATED = "updated"
    CANCELLED = "cancelled"


class AppointmentEventActor(StrEnum):
    OWNER = "owner"
    CUSTOMER = "customer"
    ABSENCE = "absence"


@versioned
class AppointmentEvent(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "appointment_events"
    __table_args__ = (
        enum_check("kind", AppointmentEventKind),
        enum_check("actor", AppointmentEventActor),
        Index("ix_appointment_events_barbershop_id_created_at", "barbershop_id", "created_at"),
    )

    barbershop_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("barbershops.id"))
    appointment_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    kind: Mapped[AppointmentEventKind] = mapped_column(string_enum(AppointmentEventKind, 11))
    actor: Mapped[AppointmentEventActor] = mapped_column(string_enum(AppointmentEventActor, 8))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    previous_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
