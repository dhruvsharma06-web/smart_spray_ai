# Smart Farming Assistant Backend

Production-style FastAPI integration backend for Smart Spray. It is deliberately **not** the AI model, frontend, ESP32 firmware, or final decision engine. It orchestrates those independent modules through service interfaces.

## Architecture

Frontend → FastAPI → AI service / Weather adapter / Decision service → PostgreSQL → IoT command boundary

The API keeps AI, decision, weather, GenAI, storage, IoT command validation, persistence, authentication, and ownership checks in separate modules.

## Included

- FastAPI REST API + Swagger/OpenAPI at `/docs`
- PostgreSQL + SQLAlchemy + Alembic schema
- JWT authentication and ownership enforcement
- Users, farms, fields, devices, telemetry and history
- Image upload and analysis orchestration
- Independent AI and Decision Engine clients
- Mock AI, Decision and GenAI services
- Weather provider abstraction with mock provider
- Guarded actuator endpoints
- Alerts
- Farmer dashboard/history/risk APIs
- Local image storage abstraction
- Audit logging and request logging
- Docker Compose
- Basic tests

## Run with Docker

1. Copy `.env.example` to `.env` for local reference.
2. Run:

```bash
docker compose up --build
```

3. Open `http://localhost:8000/docs`.

The API container talks to PostgreSQL and the three mock services over the Docker network.

## Local development

Requires Python 3.12+ and PostgreSQL.

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

For a real database migration, use:

```bash
alembic upgrade head
```

## Authentication

Register:

`POST /api/auth/register`

Login uses OAuth2 form fields (`username` = email, `password`):

`POST /api/auth/login`

Use the returned bearer token in Swagger's Authorize dialog.

## IoT telemetry

`POST /api/sensors/telemetry` accepts the Smart Spray contract:

```json
{
  "device_id": "FIELD_001",
  "timestamp": "2026-09-15T08:00:00Z",
  "soil": {"moisture": 28, "temperature": 27, "ph": 6.5, "nitrogen": 42, "phosphorus": 21, "potassium": 35},
  "environment": {"temperature": 35, "humidity": 76, "rain": false},
  "tank_level": 72,
  "pump": false
}
```

Both the device timestamp and server receipt timestamp are persisted. Delayed/offline readings are therefore distinguishable.

## Analysis flow

`POST /api/analysis` accepts `field_id` plus an image. The route only validates input and delegates to `AnalysisOrchestrator`.

The orchestrator:

1. obtains latest sensor data for the field;
2. obtains weather through the provider abstraction;
3. calls the independent AI service;
4. persists structured AI results and child detections/risk;
5. calls the independent Decision Engine;
6. persists the decision;
7. creates relevant alerts;
8. returns analysis + decision + weather.

No model inference is implemented in this repository.

## Actuator safety

The backend intentionally refuses blind spray commands. `POST /api/devices/{device_id}/spray` requires a `decision_id`, and the persisted decision must authorize `SPRAY`, the device must be online, the tank must not be critically low, and confirmation/critical-risk flags block execution.

`irrigate` also requires a decision ID. `stop` remains available as the emergency command boundary.

The `execute_local` implementation is a development adapter: it records the command and toggles local device state. A production deployment should replace that adapter with the real IoT transport without changing API contracts.

## Real services

Set these environment variables to independent services:

- `AI_SERVICE_URL`
- `DECISION_SERVICE_URL`
- `GENAI_SERVICE_URL`

The expected AI endpoint is `POST /ai/analyze`; the expected Decision endpoint is `POST /decision`; the expected explanation endpoint is `POST /assistant/explain`.

## Weather provider

`WeatherService` depends on the `WeatherProvider` interface. Add a provider adapter (for example, an HTTP client for a selected weather vendor) rather than putting vendor calls in routes. The current provider is mock and returns current conditions, rainfall, forecast, rain probability, and extreme-weather information.

## Important production hardening still required before field deployment

This is a strong integration backend scaffold, not a claim of field-ready safety certification. Before controlling real agricultural equipment, add:

- real IoT command transport with device authentication and acknowledgements;
- transactional/idempotent command IDs and replay protection;
- per-device authorization and command expiry;
- TLS everywhere;
- secrets from a secret manager, not `.env` in production;
- rate limiting and request-size limits at the edge;
- object storage such as S3-compatible storage;
- real weather adapter and verified treatment data;
- background job/queue processing for slow AI analysis;
- database backups, migrations in deployment, metrics and tracing;
- hardware-side interlocks and an independent emergency-stop circuit;
- comprehensive integration, failure-injection, and security testing.

Do not treat a backend HTTP check as a substitute for hardware safety interlocks.
