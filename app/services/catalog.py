from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser
from app.core.exceptions import ConflictError, NotFoundError
from app.models.barbershop import Barbershop
from app.models.service import Service
from app.repositories.appointment import AppointmentItemRepository
from app.repositories.barbershop import BarbershopRepository
from app.repositories.service import ServiceRepository
from app.schemas.service import ServiceCreate, ServiceUpdate
from app.services.common import existing_barbershop, require_barbershop


class CatalogService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.barbershops = BarbershopRepository(session)
        self.services = ServiceRepository(session)

    async def create(self, user: AuthenticatedUser, data: ServiceCreate) -> Service:
        barbershop = await require_barbershop(self.barbershops, user)
        await self._ensure_name_available(barbershop, data.name)
        return await self._persist(
            self.services.add(Service(barbershop_id=barbershop.id, **data.model_dump()))
        )

    async def list(
        self,
        user: AuthenticatedUser,
        *,
        offset: int,
        limit: int,
        search: str | None,
        active: bool | None,
    ) -> tuple[Sequence[Service], int]:
        barbershop = await require_barbershop(self.barbershops, user)
        return await self.services.list_for_barbershop(
            barbershop.id, offset=offset, limit=limit, search=search, active=active
        )

    async def list_public(
        self, barbershop_id: UUID, *, offset: int, limit: int
    ) -> tuple[Sequence[Service], int]:
        await existing_barbershop(self.barbershops, barbershop_id)
        return await self.services.list_for_barbershop(
            barbershop_id, offset=offset, limit=limit, active=True
        )

    async def get(self, user: AuthenticatedUser, service_id: UUID) -> Service:
        barbershop = await require_barbershop(self.barbershops, user)
        return await self._owned(barbershop, service_id)

    async def update(
        self, user: AuthenticatedUser, service_id: UUID, data: ServiceUpdate
    ) -> Service:
        barbershop = await require_barbershop(self.barbershops, user)
        service = await self._owned(barbershop, service_id)
        changes = data.model_dump(exclude_unset=True)
        if "name" in changes and changes["name"].lower() != service.name.lower():
            await self._ensure_name_available(barbershop, changes["name"])
        for field, value in changes.items():
            setattr(service, field, value)
        return await self._persist(self.services.save(service))

    async def delete(self, user: AuthenticatedUser, service_id: UUID) -> None:
        barbershop = await require_barbershop(self.barbershops, user)
        service = await self._owned(barbershop, service_id)
        if await AppointmentItemRepository(self.session).is_service_used(service.id):
            raise ConflictError("Service is used by appointments; deactivate it instead")
        await self.services.delete(service)
        await self.session.commit()

    async def _owned(self, barbershop: Barbershop, service_id: UUID) -> Service:
        service = await self.services.get_by(id=service_id, barbershop_id=barbershop.id)
        if service is None:
            raise NotFoundError(f"Service {service_id} not found")
        return service

    async def _ensure_name_available(self, barbershop: Barbershop, name: str) -> None:
        if await self.services.get_by_name(barbershop.id, name) is not None:
            raise ConflictError(f"Service '{name}' already exists")

    async def _persist(self, operation) -> Service:
        try:
            service = await operation
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Service name already exists") from exc
        return service
