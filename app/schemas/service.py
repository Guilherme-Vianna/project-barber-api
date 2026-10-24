from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from app.schemas.types import Price, PriceValue

ServiceName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class ServiceCreate(BaseModel):
    name: ServiceName
    price: Price
    active: bool = True


class ServiceUpdate(BaseModel):
    name: ServiceName | None = None
    price: Price | None = None
    active: bool | None = None

    @model_validator(mode="after")
    def reject_nulls(self) -> Self:
        nulls = sorted(field for field in self.model_fields_set if getattr(self, field) is None)
        if nulls:
            raise ValueError(f"Fields cannot be null: {', '.join(nulls)}")
        return self


class ServicePublicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    price: PriceValue


class ServiceRead(ServicePublicRead):
    active: bool
    created_at: datetime
    updated_at: datetime
