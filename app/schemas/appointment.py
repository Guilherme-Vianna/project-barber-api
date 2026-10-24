from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.models.appointment_event import AppointmentEventActor, AppointmentEventKind
from app.schemas.types import FirstName, LastName, PriceValue

ServiceIds = Annotated[list[UUID], Field(min_length=1, max_length=20)]


def _unique(ids: list[UUID] | None) -> None:
    if ids is not None and len(set(ids)) != len(ids):
        raise ValueError("service_ids must not repeat")


class AppointmentCreate(BaseModel):
    starts_at: AwareDatetime
    first_name: FirstName
    last_name: LastName | None = None
    service_ids: ServiceIds

    @model_validator(mode="after")
    def check_services(self) -> Self:
        _unique(self.service_ids)
        return self


class AppointmentUpdate(BaseModel):
    starts_at: AwareDatetime | None = None
    first_name: FirstName | None = None
    last_name: LastName | None = None
    service_ids: ServiceIds | None = None

    @model_validator(mode="after")
    def check_fields(self) -> Self:
        nullable = {"last_name"}
        nulls = sorted(
            field for field in self.model_fields_set - nullable if getattr(self, field) is None
        )
        if nulls:
            raise ValueError(f"Fields cannot be null: {', '.join(nulls)}")
        _unique(self.service_ids)
        return self


class AppointmentItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    service_id: UUID
    name: str
    price: PriceValue


class AppointmentPublicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    starts_at: datetime
    ends_at: datetime


class AppointmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str | None
    starts_at: datetime
    ends_at: datetime
    items: list[AppointmentItemRead]
    total: PriceValue
    created_at: datetime
    updated_at: datetime


class BookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    barbershop_id: UUID
    barbershop_name: str
    first_name: str
    last_name: str | None
    starts_at: datetime
    ends_at: datetime
    items: list[AppointmentItemRead]
    total: PriceValue


class BookingReschedule(BaseModel):
    starts_at: AwareDatetime


class AppointmentEventPublicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: AppointmentEventKind
    actor: AppointmentEventActor
    starts_at: datetime
    previous_starts_at: datetime | None
    created_at: datetime


class AppointmentEventRead(AppointmentEventPublicRead):
    id: UUID
    appointment_id: UUID
