from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base


class BaseRepository[ModelT: Base]:
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, entity_id: UUID) -> ModelT | None:
        return await self.session.get(self.model, entity_id)

    async def get_by(self, **criteria: Any) -> ModelT | None:
        return await self.session.scalar(select(self.model).filter_by(**criteria).limit(1))

    async def find_by(self, **criteria: Any) -> Sequence[ModelT]:
        stmt = select(self.model).filter_by(**criteria).order_by(self.model.id)
        return (await self.session.scalars(stmt)).all()

    async def list(self, *, offset: int = 0, limit: int = 50) -> Sequence[ModelT]:
        stmt = select(self.model).order_by(self.model.id).offset(offset).limit(limit)
        result = await self.session.scalars(stmt)
        return result.all()

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self.model)
        return (await self.session.scalar(stmt)) or 0

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def save(self, entity: ModelT) -> ModelT:
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def delete(self, entity: ModelT) -> None:
        await self.session.delete(entity)
        await self.session.flush()
