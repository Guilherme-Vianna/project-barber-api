from decimal import Decimal
from typing import Annotated

from pydantic import Field, PlainSerializer, StringConstraints

FirstName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
BarbershopName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)
]
LastName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
PriceValue = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
Price = Annotated[PriceValue, Field(ge=0, max_digits=10, decimal_places=2)]
