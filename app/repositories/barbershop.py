from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select

from app.models.barbershop import Barbershop
from app.repositories.base import BaseRepository


class BarbershopRepository(BaseRepository[Barbershop]):
    model = Barbershop

    async def get_by_firebase_uid(self, firebase_uid: str) -> Barbershop | None:
        return await self.get_by(firebase_uid=firebase_uid)

    async def lock(self, barbershop_id: UUID) -> None:
        await self.session.execute(
            select(Barbershop.id).where(Barbershop.id == barbershop_id).with_for_update()
        )

    async def lock_uid(self, firebase_uid: str) -> None:
        await self.session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(firebase_uid, 0)))
        )

    async def list_sorted(self, *, offset: int, limit: int) -> tuple[Sequence[Barbershop], int]:
        stmt = select(Barbershop).order_by(func.lower(Barbershop.name), Barbershop.id)
        items = (await self.session.scalars(stmt.offset(offset).limit(limit))).all()
        return items, await self.count()
