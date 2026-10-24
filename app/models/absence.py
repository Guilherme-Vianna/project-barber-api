from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDv7PrimaryKeyMixin
from app.models.history import versioned


@versioned
class Absence(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "absences"
    __table_args__ = (CheckConstraint("ends_at > starts_at", name="period"),)

    barbershop_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("barbershops.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
