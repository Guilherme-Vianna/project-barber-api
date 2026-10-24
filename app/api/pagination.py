from collections.abc import Iterable
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Query
from pydantic import BaseModel

from app.schemas.common import Page


@dataclass(frozen=True, slots=True)
class Pagination:
    offset: int
    limit: int


def get_pagination(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Pagination:
    return Pagination(offset=offset, limit=limit)


PaginationDep = Annotated[Pagination, Depends(get_pagination)]


def to_page[SchemaT: BaseModel](
    schema: type[SchemaT], result: tuple[Iterable[Any], int], pagination: Pagination
) -> Page[SchemaT]:
    items, total = result
    return Page[schema](
        items=[schema.model_validate(item) for item in items],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )
