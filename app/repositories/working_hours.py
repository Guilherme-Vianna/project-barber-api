from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from app.models.working_hours import WorkingHours
from app.repositories.base import BaseRepository


class WorkingHoursRepository(BaseRepository[WorkingHours]):
    model = WorkingHours

    async def for_barbershop(self, barbershop_id: UUID) -> Sequence[WorkingHours]:
        stmt = (
            select(WorkingHours)
            .where(WorkingHours.barbershop_id == barbershop_id)
            .order_by(WorkingHours.weekday)
            .execution_options(populate_existing=True)
        )
        return (await self.session.scalars(stmt)).all()
