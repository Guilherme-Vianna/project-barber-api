from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator


class AbsenceCreate(BaseModel):
    starts_at: AwareDatetime
    ends_at: AwareDatetime

    @model_validator(mode="after")
    def check_period(self) -> Self:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class AbsencePublicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    starts_at: datetime
    ends_at: datetime


class AbsenceRead(AbsencePublicRead):
    id: UUID
    created_at: datetime


class AbsenceCreated(AbsenceRead):
    cancelled_appointments: int
