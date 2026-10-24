from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.schemas.types import BarbershopName, FirstName, LastName


class BarbershopCreate(BaseModel):
    name: BarbershopName
    first_name: FirstName
    last_name: LastName


class BarbershopUpdate(BaseModel):
    name: BarbershopName | None = None
    first_name: FirstName | None = None
    last_name: LastName | None = None

    @model_validator(mode="after")
    def reject_nulls(self) -> Self:
        nulls = sorted(field for field in self.model_fields_set if getattr(self, field) is None)
        if nulls:
            raise ValueError(f"Fields cannot be null: {', '.join(nulls)}")
        return self


class BarbershopPublicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    first_name: str
    last_name: str


class BarbershopRead(BarbershopPublicRead):
    created_at: datetime
    updated_at: datetime
