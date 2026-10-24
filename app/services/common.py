from uuid import UUID

from app.core.auth import AuthenticatedUser
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.barbershop import Barbershop
from app.repositories.barbershop import BarbershopRepository


async def require_barbershop(
    barbershops: BarbershopRepository, user: AuthenticatedUser
) -> Barbershop:
    barbershop = await barbershops.get_by_firebase_uid(user.uid)
    if barbershop is None:
        raise ForbiddenError("Register a barbershop before performing this action")
    return barbershop


async def existing_barbershop(barbershops: BarbershopRepository, barbershop_id: UUID) -> Barbershop:
    barbershop = await barbershops.get(barbershop_id)
    if barbershop is None:
        raise NotFoundError(f"Barbershop {barbershop_id} not found")
    return barbershop
