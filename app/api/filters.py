from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query
from pydantic import AwareDatetime

from app.core.exceptions import UnprocessableError


@dataclass(frozen=True, slots=True)
class Period:
    starts_from: AwareDatetime | None
    starts_until: AwareDatetime | None


def get_period(
    starts_from: Annotated[AwareDatetime | None, Query(alias="from")] = None,
    starts_until: Annotated[AwareDatetime | None, Query(alias="to")] = None,
) -> Period:
    if starts_from and starts_until and starts_until <= starts_from:
        raise UnprocessableError("'to' must be after 'from'")
    return Period(starts_from=starts_from, starts_until=starts_until)


PeriodDep = Annotated[Period, Depends(get_period)]
