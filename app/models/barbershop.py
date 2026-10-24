from sqlalchemy import CheckConstraint, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDv7PrimaryKeyMixin
from app.models.history import versioned


@versioned
class Barbershop(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "barbershops"
    __table_args__ = (CheckConstraint("slot_minutes BETWEEN 5 AND 480", name="slot_minutes"),)

    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(150))
    slot_minutes: Mapped[int] = mapped_column(Integer, default=30, server_default=text("30"))
