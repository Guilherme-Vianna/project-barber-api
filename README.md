# project-barber-api

Barbershop appointment API built with FastAPI and a classic three-layer architecture (API → Service → Repository), PostgreSQL via SQLAlchemy 2.0 async, Firebase Authentication, SCD Type 4 history tables, UUIDv7 primary keys and a Dockerfile ready for Google Cloud Run.

## Stack

- Python 3.14 (native `uuid.uuid7()`)
- FastAPI + Uvicorn
- SQLAlchemy 2.0 (async) + asyncpg + Alembic
- Pydantic v2 + pydantic-settings
- Firebase Admin SDK (barbershop owner authentication)
- Redis (optional response cache)
- uv for dependency management
- pytest + httpx, ruff

## Local development

```bash
cp .env.example .env
docker compose up -d db
uv sync
uv run alembic upgrade head
uv run task dev
```

Docs: http://localhost:8080/docs

Redis is optional. To enable the response cache locally, run `docker compose up -d redis` and set `REDIS_URL=redis://localhost:6379/0` in `.env`.

## Data model

| Table | Columns |
| --- | --- |
| `barbershops` | `name`, `first_name`, `last_name`, `slot_minutes`, `firebase_uid` (owner) |
| `services` | `barbershop_id`, `name`, `price`, `active` |
| `working_hours` | `barbershop_id`, `weekday` (0 = Monday), `opens_at`, `closes_at` (one row per open weekday) |
| `absences` | `barbershop_id`, `starts_at`, `ends_at` |
| `appointments` | `barbershop_id`, `starts_at`, `ends_at`, `first_name`, `last_name` (optional), `customer_token_hash` |
| `appointment_events` | `appointment_id`, `kind`, `actor`, `starts_at`, `previous_starts_at` (change log) |
| `appointment_services` | `appointment_id`, `service_id`, `price` (snapshot at booking time) |

Every table has a `<table>_history` companion (SCD Type 4) recording each insert, update and delete.

## Authentication

Barbershop owners sign in with Firebase and send `Authorization: Bearer <id-token>`. Customers do not need an account: they browse barbershops and book publicly with their name.

## Endpoints

Public:

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/v1/barbershops` | List barbershops |
| GET | `/api/v1/barbershops/{id}` | Barbershop details |
| GET | `/api/v1/barbershops/{id}/services` | Active services |
| GET | `/api/v1/barbershops/{id}/schedule` | Horário de atendimento: weekdays, hours, slot length |
| GET | `/api/v1/barbershops/{id}/appointments?from=&to=` | Booked times only (`starts_at`, `ends_at`) |
| GET | `/api/v1/barbershops/{id}/absences?from=&to=` | Blocked intervals |
| POST | `/api/v1/barbershops/{id}/appointments` | Book `{starts_at, first_name, last_name?, service_ids}` (needs `X-Customer-Token`) |
| GET / PATCH / DELETE | `/api/v1/barbershops/{id}/my-booking` | Customer (`X-Customer-Token`): view, reschedule `{starts_at}`, cancel the upcoming booking |
| GET | `/api/v1/barbershops/{id}/my-booking/events` | Customer: change log of that booking |

Owner (bearer token):

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/v1/barbershops` | Register the current user's barbershop |
| GET / PATCH / DELETE | `/api/v1/barbershops/me` | Own barbershop (DELETE purges all its data) |
| POST / GET | `/api/v1/services` | Create / list services (`search`, `active`) |
| GET / PATCH / DELETE | `/api/v1/services/{id}` | Manage a service (used services: deactivate instead of delete) |
| GET / PUT | `/api/v1/schedule` | Horário de atendimento: `{slot_minutes, days: [{weekday, opens_at, closes_at}]}`; days left out are closed |
| POST / GET | `/api/v1/absences` | Block an interval (cancels overlapping appointments) / list (`from`, `to`) |
| DELETE | `/api/v1/absences/{id}` | Remove an absence |
| POST / GET | `/api/v1/appointments` | Create (walk-in) / list appointments (`from`, `to`) |
| GET | `/api/v1/appointment-events` | Change log, newest first (`appointment_id`, `from`, `to` on `created_at`) |
| GET / PATCH / DELETE | `/api/v1/appointments/{id}` | View, change time/names/services, cancel |

List endpoints are paginated with `offset` and `limit` (max 100). Datetimes must include a timezone offset.

## Business rules

- `name` is the barbershop name; `first_name`/`last_name` are the owner's.
- The owner sets the weekdays worked (it repeats every week, no end date), opening and closing times and one slot length; blocks are built by the client and never stored (in `TIME_ZONE`).
- Appointments of the same barbershop cannot overlap; only future, on-grid times of open days of open days can be booked.
- An absence cancels every appointment inside its interval and blocks new bookings there.
- Everyone shares the same link; each browser keeps a random device token (`X-Customer-Token`). A device has at most one
  upcoming booking per barbershop, which it can view, reschedule or cancel; after it starts the device can book again.
- Every booking, reschedule, update and cancellation is logged in `appointment_events` with who did it.
- Appointment prices are copied from the service when booked, so later price changes do not affect existing appointments.

## Response cache

When `REDIS_URL` is set, successful `GET /api/v1/...` responses are cached in Redis, keyed by bearer token (or anonymous), path and query string. Cached responses carry `X-Cache: HIT`. Any write bumps a version for each table it touched, which invalidates every cached response that read those tables, for all users. Entries live at most `CACHE_TTL_SECONDS` (default 600), never beyond the token expiry. Without `REDIS_URL` (the default) the cache is off and requests go straight to the database. If Redis is configured but unreachable, the first failing request logs a warning and the API bypasses Redis for 30 seconds before retrying; when Redis comes back, every entry cached before the outage is invalidated.

## Tests

```bash
docker compose up -d db
uv run pytest
```

## Deployment

`.github/workflows/deploy.yml` runs lint, tests and `alembic check` on every PR and deploys `main` to Cloud Run in `southamerica-east1`. Only the `GCP_CREDENTIALS` and `DATABASE_URL` secrets (plus optional `REDIS_URL`) are required in the `development` environment; the project id comes from the credentials. Optional variables: `CLOUD_RUN_SERVICE` and `GAR_REPOSITORY` (default `project-barber-api`; the repository is created if missing), `GCP_SERVICE_ACCOUNT`, `FIREBASE_PROJECT_ID` (defaults to the GCP project).
