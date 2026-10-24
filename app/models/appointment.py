from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDv7PrimaryKeyMixin
from app.models.history import versioned
from app.models.service import PRICE, Service


@versioned
class Appointment(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "appointments"
    __table_args__ = (
        UniqueConstraint("barbershop_id", "starts_at"),
        CheckConstraint("ends_at > starts_at", name="period"),
    )

    barbershop_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("barbershops.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(150))
    customer_token_hash: Mapped[str | None] = mapped_column(String(64), index=True)

    items: Mapped[list[AppointmentItem]] = relationship(
        viewonly=True, lazy="raise", order_by="AppointmentItem.id"
    )

    @property
    def total(self) -> Decimal:
        return sum((item.price for item in self.items), Decimal(0))


@versioned
class AppointmentItem(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "appointment_services"
    __table_args__ = (
        UniqueConstraint("appointment_id", "service_id"),
        CheckConstraint("price >= 0", name="price"),
    )

    appointment_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("appointments.id"))
    service_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("services.id"), index=True)
    price: Mapped[Decimal] = mapped_column(PRICE)

    service: Mapped[Service] = relationship(viewonly=True, lazy="raise")

    @property
    def name(self) -> str:
        return self.service.name
