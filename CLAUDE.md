# CLAUDE.md

## Rules for the AI

- Keep this file 100% accurate (update it with any structure/stack/command/convention change); max 100 lines.
- English everywhere (code, identifiers, docs, commits); no code comments/docstrings (strip Alembic's too).
- Every new environment variable goes into `.env.example`, `Settings` and the deploy workflow's jq env file.

## Project

Barbershop appointment REST API (FastAPI, three layers), PostgreSQL, Firebase Auth, Redis, Cloud Run; mirrors `project-study-api`.

- Python 3.14, uv (`package = false`), taskipy (`uv run task dev`); FastAPI, Pydantic v2, firebase-admin, tzdata, redis
- SQLAlchemy 2.0 async + asyncpg, Alembic; primary keys are UUIDv7 via stdlib `uuid.uuid7`
- Tests: pytest + pytest-asyncio (auto) + httpx against real Postgres (`app_test`); Firebase and Redis are faked

## Domain rules

- Firebase Auth is the only user source (no users table). One Firebase user owns at most one barbershop
  (`barbershops.firebase_uid`); registration takes a Postgres advisory lock on the uid.
- Barbershop: `name` (not unique), owner `first_name`/`last_name`. Period filters: `from`/`to` (`api/filters.PeriodDep`).
- Services (`services`): `name` (unique per barbershop ignoring case), `price` `Numeric(10,2)` ↔ `schemas/types.Price`,
  `active`. Used services cannot be deleted (409) — deactivate them; inactive ones are hidden publicly and not bookable.
- Horário de atendimento (weekly, no end date): `working_hours` (weekday 0=Monday..6, `opens_at`, `closes_at`; missing
  weekday = closed) + `barbershops.slot_minutes` (5..480), replaced via `PUT /schedule`. Blocks are never stored:
  clients build them. `services/availability` validates every start (in `TIME_ZONE`): open weekday, on the grid,
  future, no overlap with appointments or absences.
- Absences (`absences`): interval; `POST /absences` cancels overlapping appointments and blocks it; `DELETE` reopens.
- Appointments (`appointments`): `barbershop_id`, `starts_at`/`ends_at` (end = start + `slot_minutes`), `first_name`,
  optional `last_name`; no overlap per barbershop (row lock on the barbershop + check, unique start as backstop).
  `appointment_services` (`AppointmentItem`) snapshot the service `price` at booking time; `total` is their sum.
  Booking needs a valid start (see schedule) and >= 1 distinct active owned service. PATCH syncs services in place
  (kept items keep their price) and `starts_at` reschedules it. DELETE cancels.
- Customer device: the browser generates a random token (`X-Customer-Token`, 32..128 `[A-Za-z0-9_-]`, `CustomerTokenDep`);
  only its SHA-256 (`customer_token_hash`) is stored. Booking requires it; one upcoming booking per device and shop
  (409). `/barbershops/{id}/my-booking`: GET, PATCH `starts_at`, DELETE, GET `/events` (the next future one; cache key
  includes the header). Once it starts the device can book again. Walk-ins have no token.
- Change log (`appointment_events`): every booking, reschedule, update and cancellation records `kind`, `actor`
  (owner/customer/absence), `starts_at`, `previous_starts_at`; no FK to the appointment. Owner: `GET /appointment-events`.
- Public (no token): `GET /barbershops`, `GET /barbershops/{id}`, `.../services` (active), `.../schedule`,
  `.../appointments` (times only), `.../absences`, `POST .../appointments` (booking; history `changed_by` is NULL),
  `.../my-booking`. Everything else needs a token.
- Owner routes act on the caller's shop (`services/common.require_barbershop` → 403); other shops' rows → 404.
- Unregistering purges appointments (items first), events, absences, working hours, services, then the barbershop.

## SCD Type 4

- Every entity uses `@versioned` (`app/models/history.py`) creating `<table>_history`: entity columns + `history_id`,
  `operation`, `valid_from`, `valid_to` (NULL = open version), `changed_by` (`session.info["actor"]`, the uid).
- An `after_flush` listener writes history. Always mutate through the ORM; bulk statements and DB cascades bypass it.
- Columns need explicit types (FKs: `mapped_column(Uuid, ForeignKey(...))`). `tests/test_history.py` enforces versioning.

## Layout

```
app/
  core/          config, database, auth (IdentityProvider), cache (ResponseCache), exceptions, migrations
  integrations/  firebase.py (identity), redis.py (response cache)
  api/           deps, pagination, filters (PeriodDep), cache (middleware), health, v1/endpoints/*
  models/ schemas/ repositories/  one module per resource: barbershop, service, working_hours, absence, appointment(_event)
  services/      barbershop, catalog (CatalogService = barber services), schedule, availability, absence, appointment, common
alembic/         async env.py, versions/ (ruff post-write hooks)
tests/           conftest, fakes (identity + cache), helpers, one module per resource
docker/          postgres/init (app_test DB); compose also runs redis
.github/         workflows/deploy.yml (CI + Cloud Run deploy)
```

## Layer rules

- CORS: `CORS_ORIGINS` (comma-separated, default `*`) feeds `CORSMiddleware` in `create_app`.
- Response cache (`api/cache.py`, `core/cache.py`; off without `REDIS_URL`): v1 GET 200s keyed by token (or anonymous)
  + path + query; TTL ≤ `CACHE_TTL_SECONDS`, the token `exp` and `cache_until`. ORM listeners track tables read/written;
  writes bump table versions. A Redis failure bypasses it for `BACKOFF_SECONDS`; the next successful contact resets
  the epoch, invalidating everything cached before the outage.
- Endpoints parse input, call a service, map to schemas. Owner deps use `AuditedSessionDep`; public deps `SessionDep`.
- Services own rules, raise `AppError` subclasses (never `HTTPException`) and commit.
- Repositories only touch the session; never commit. Relationships are `viewonly`, `lazy="raise"`; load aggregates
  with selectinload + `populate_existing` (`appointment_aggregate_options`).
- External services only via `IdentityProvider` / `ResponseCache`; tests override `get_identity_provider`/`get_response_cache`.
- New entity: model + `@versioned` → `models/__init__` → schema → repository → service → deps → endpoint → migration → tests.

## Commands

```bash
docker compose up -d db          # + redis, with REDIS_URL=redis://localhost:6379/0 in .env
uv sync
uv run alembic upgrade head
uv run task dev
uv run pytest
uv run ruff check . && uv run ruff format .
uv run alembic revision --autogenerate -m "message" && uv run alembic check
```

## Deployment

- GitHub Actions: PRs run lint + tests + `alembic check`; pushes to `main` build → Artifact Registry → deploy → smoke
  test. The app creates the database if missing and migrates on startup (`RUN_MIGRATIONS_ON_STARTUP`). Auth via SA key
  secret `GCP_CREDENTIALS`; `DATABASE_URL`/`REDIS_URL` secrets; `development` env vars; `K_REVISION` namespaces cache.
- `DATABASE_URL` accepts provider URLs (`postgresql://…?sslmode=…&channel_binding=…`); `Settings` normalizes for asyncpg.
- `Dockerfile`: multi-stage uv, `python:3.14-slim`, non-root, `$PORT`; no BuildKit-only features.
