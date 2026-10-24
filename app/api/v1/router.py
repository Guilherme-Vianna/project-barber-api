from fastapi import APIRouter

from app.api.v1.endpoints import (
    absences,
    appointment_events,
    appointments,
    barbershops,
    schedule,
    services,
)

api_router = APIRouter()
api_router.include_router(barbershops.router)
api_router.include_router(services.router)
api_router.include_router(absences.router)
api_router.include_router(schedule.router)
api_router.include_router(appointments.router)
api_router.include_router(appointment_events.router)
