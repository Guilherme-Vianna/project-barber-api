from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDv7PrimaryKeyMixin
from app.models.history import versioned

PRICE = Numeric(10, 2)


@versioned
class Service(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint("barbershop_id", "name"),
        CheckConstraint("price >= 0", name="price"),
    )

    barbershop_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("barbershops.id"))
    name: Mapped[str] = mapped_column(String(100))
    price: Mapped[Decimal] = mapped_column(PRICE)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
