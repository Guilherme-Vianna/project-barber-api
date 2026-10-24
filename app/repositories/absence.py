from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, func, select

from app.models.absence import Absence
from app.repositories.base import BaseRepository


class AbsenceRepository(BaseRepository[Absence]):
    model = Absence

    async def get_owned(self, barbershop_id: UUID, absence_id: UUID) -> Absence | None:
        return await self.get_by(id=absence_id, barbershop_id=barbershop_id)

    async def list_for_barbershop(
        self,
        barbershop_id: UUID,
        *,
        offset: int,
        limit: int,
        starts_from: datetime | None = None,
        starts_until: datetime | None = None,
    ) -> tuple[Sequence[Absence], int]:
        conditions: list[ColumnElement[bool]] = [Absence.barbershop_id == barbershop_id]
        if starts_from is not None:
            conditions.append(Absence.ends_at > starts_from)
        if starts_until is not None:
            conditions.append(Absence.starts_at < starts_until)
        stmt = select(Absence).where(*conditions).order_by(Absence.starts_at, Absence.id)
        items = (await self.session.scalars(stmt.offset(offset).limit(limit))).all()
        total = await self.session.scalar(select(func.count(Absence.id)).where(*conditions))
        return items, total or 0

    async def overlaps(self, barbershop_id: UUID, starts_at: datetime, ends_at: datetime) -> bool:
        conditions = [
            Absence.barbershop_id == barbershop_id,
            Absence.starts_at < ends_at,
            Absence.ends_at > starts_at,
        ]
        stmt = select(select(Absence.id).where(*conditions).exists())
        return bool(await self.session.scalar(stmt))
