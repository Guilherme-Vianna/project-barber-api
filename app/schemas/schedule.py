from datetime import time
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

SlotMinutes = Annotated[int, Field(ge=5, le=480)]
Weekday = Annotated[int, Field(ge=0, le=6)]


class WorkingDay(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    weekday: Weekday
    opens_at: time
    closes_at: time

    @model_validator(mode="after")
    def check_period(self) -> Self:
        if self.closes_at <= self.opens_at:
            raise ValueError("closes_at must be after opens_at")
        return self


class ScheduleUpdate(BaseModel):
    slot_minutes: SlotMinutes
    days: Annotated[list[WorkingDay], Field(max_length=7)]

    @model_validator(mode="after")
    def check_days(self) -> Self:
        weekdays = [day.weekday for day in self.days]
        if len(set(weekdays)) != len(weekdays):
            raise ValueError("weekdays must not repeat")
        return self


class ScheduleRead(BaseModel):
    slot_minutes: int
    days: list[WorkingDay]
