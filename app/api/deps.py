from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser, IdentityProvider
from app.core.database import get_session
from app.core.exceptions import UnauthorizedError
from app.integrations.firebase import get_identity_provider
from app.models.history import ACTOR_KEY
from app.services.absence import AbsenceService
from app.services.appointment import AppointmentService
from app.services.barbershop import BarbershopService
from app.services.catalog import CatalogService
from app.services.schedule import ScheduleService

bearer_scheme = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]
IdentityDep = Annotated[IdentityProvider, Depends(get_identity_provider)]
CredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


async def get_current_user(credentials: CredentialsDep, identity: IdentityDep) -> AuthenticatedUser:
    if credentials is None:
        raise UnauthorizedError("Missing bearer token")
    return await identity.verify_token(credentials.credentials)


CurrentUserDep = Annotated[AuthenticatedUser, Depends(get_current_user)]

CUSTOMER_TOKEN_PATTERN = r"^[A-Za-z0-9_-]{32,128}$"

CustomerTokenDep = Annotated[str, Header(alias="X-Customer-Token", pattern=CUSTOMER_TOKEN_PATTERN)]


def get_audited_session(session: SessionDep, user: CurrentUserDep) -> AsyncSession:
    session.info[ACTOR_KEY] = user.uid
    return session


AuditedSessionDep = Annotated[AsyncSession, Depends(get_audited_session)]


def get_public_barbershop_service(session: SessionDep) -> BarbershopService:
    return BarbershopService(session)


PublicBarbershopServiceDep = Annotated[BarbershopService, Depends(get_public_barbershop_service)]


def get_barbershop_service(session: AuditedSessionDep) -> BarbershopService:
    return BarbershopService(session)


BarbershopServiceDep = Annotated[BarbershopService, Depends(get_barbershop_service)]


def get_public_catalog_service(session: SessionDep) -> CatalogService:
    return CatalogService(session)


PublicCatalogServiceDep = Annotated[CatalogService, Depends(get_public_catalog_service)]


def get_catalog_service(session: AuditedSessionDep) -> CatalogService:
    return CatalogService(session)


CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]


def get_public_absence_service(session: SessionDep) -> AbsenceService:
    return AbsenceService(session)


PublicAbsenceServiceDep = Annotated[AbsenceService, Depends(get_public_absence_service)]


def get_absence_service(session: AuditedSessionDep) -> AbsenceService:
    return AbsenceService(session)


AbsenceServiceDep = Annotated[AbsenceService, Depends(get_absence_service)]


def get_public_schedule_service(session: SessionDep) -> ScheduleService:
    return ScheduleService(session)


PublicScheduleServiceDep = Annotated[ScheduleService, Depends(get_public_schedule_service)]


def get_schedule_service(session: AuditedSessionDep) -> ScheduleService:
    return ScheduleService(session)


ScheduleServiceDep = Annotated[ScheduleService, Depends(get_schedule_service)]


def get_public_appointment_service(session: SessionDep) -> AppointmentService:
    return AppointmentService(session)


PublicAppointmentServiceDep = Annotated[AppointmentService, Depends(get_public_appointment_service)]


def get_appointment_service(session: AuditedSessionDep) -> AppointmentService:
    return AppointmentService(session)


AppointmentServiceDep = Annotated[AppointmentService, Depends(get_appointment_service)]
