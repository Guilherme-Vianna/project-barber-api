from pydantic import BaseModel


class Page[T](BaseModel):
    items: list[T]
    total: int
    offset: int
    limit: int
