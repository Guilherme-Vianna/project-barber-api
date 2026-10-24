from collections.abc import Iterable, Sequence
from uuid import UUID

from sqlalchemy import func, select

from app.models.service import Service
from app.repositories.base import BaseRepository


class ServiceRepository(BaseRepository[Service]):
    model = Service

    async def get_by_name(self, barbershop_id: UUID, name: str) -> Service | None:
        return await self.session.scalar(
            select(Service).where(
                Service.barbershop_id == barbershop_id, func.lower(Service.name) == name.lower()
            )
        )

    async def list_for_barbershop(
        self,
        barbershop_id: UUID,
        *,
        offset: int,
        limit: int,
        search: str | None = None,
        active: bool | None = None,
    ) -> tuple[Sequence[Service], int]:
        conditions = [Service.barbershop_id == barbershop_id]
        if search:
            conditions.append(Service.name.icontains(search, autoescape=True))
        if active is not None:
            conditions.append(Service.active.is_(active))
        stmt = select(Service).where(*conditions).order_by(func.lower(Service.name))
        items = (await self.session.scalars(stmt.offset(offset).limit(limit))).all()
        total = await self.session.scalar(select(func.count()).where(*conditions)) or 0
        return items, total

    async def find_for_barbershop(
        self, barbershop_id: UUID, ids: Iterable[UUID]
    ) -> dict[UUID, Service]:
        wanted = set(ids)
        if not wanted:
            return {}
        stmt = select(Service).where(Service.barbershop_id == barbershop_id, Service.id.in_(wanted))
        return {service.id: service for service in (await self.session.scalars(stmt)).all()}
