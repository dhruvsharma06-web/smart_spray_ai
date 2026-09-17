# Smart Spray — Person 4: Backend & Integration Prototype Guide

This document describes the **Person 4 lightweight prototype backend** using **SQLite** (`smart_spray.db`). The backend connects the **Flutter Android Frontend**, **Person 1 AI Service** (`:8001`), **Person 3 Decision Engine** (`:8002`), and a **Mock IoT Actuator** safety interface.

---

## 1. Quick Start: Running the Complete System

### Step 1: Start Person 1 AI Service (Port 8001)
```powershell
# From repository root
uvicorn ai.api:app --host 0.0.0.0 --port 8001
```

### Step 2: Start Person 3 Decision Engine (Port 8002)
```powershell
# From repository root
uvicorn decision.api:app --host 0.0.0.0 --port 8002
```

### Step 3: Start Person 4 Prototype Backend (Port 8000)
```powershell
# In backend directory
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 2. Configuration & Environment Variables

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `sqlite+aiosqlite:///./smart_spray.db` | Async SQLite connection string |
| `AI_SERVICE_URL` | `http://localhost:8001` | URL of Person 1 AI Service |
| `DECISION_SERVICE_URL`| `http://localhost:8002` | URL of Person 3 Decision Engine |
| `DEMO_MODE` | `true` | When true, enables deterministic demo scenarios |
| `DEMO_DEFAULT_SCENARIO`| `TOMATO_EARLY_BLIGHT` | Fallback scenario if none provided in request |
| `DECISION_TTL_SECONDS` | `300` | Expiry TTL for authorized decisions (5 minutes) |
| `CORS_ORIGINS` | `["*"]` | Allowed CORS origins for Flutter app |

---

## 3. SQLite Database Layer

* **Location:** `backend/smart_spray.db` (automatically initialized upon backend startup).
* **Git Status:** Ignored by `.gitignore` (database files are never committed).
* **Entities:**
  * `fields`: Field registry (`id`, `name`, `crop_type`, `latitude`, `longitude`, `created_at`)
  * `zones`: Field boundary polygons (`id`, `field_id`, `name`, `boundary_json`)
  * `devices`: Controller state (`id`, `field_id`, `name`, `status`, `battery`, `tank_level`, `current_action`, `last_seen`)
  * `telemetry`: Environmental telemetry snapshots (`id`, `field_id`, `device_id`, `soil_moisture`, `temperatures`, `humidity`, `rainfall`)
  * `analyses`: AI diagnostic records (`id`, `field_id`, `raw_ai_result_json`, `image_metadata`)
  * `decisions`: Agronomic decisions with TTL (`id`, `analysis_id`, `primary_decision`, `risk_level`, `expires_at`, `requires_confirmation`)
  * `action_history`: Actuator command audit log (`id`, `device_id`, `decision_id`, `action`, `status`, `duration_ms`, `volume_ml`, `message`)

---

## 4. API Endpoints

### Canonical Endpoints
* `POST /fields`: Register new agricultural field.
* `POST /devices`: Register or bind an IoT controller to a field.
* `POST /telemetry`: Ingest soil and atmospheric sensor telemetry.
* `GET /fields/{id}/latest`: Retrieve latest combined field state (telemetry, analysis, decision).
* `GET /fields/{id}/history`: Retrieve chronological analysis and actuation history.
* `GET /fields/{id}/zones`: Retrieve zone boundary coordinates.
* `GET /devices/{id}/status`: Query real-time device battery, tank level, and operational state.
* `POST /devices/{id}/command`: Dispatch operational or emergency commands to hardware.
* `POST /analyze`: Central end-to-end diagnosis and actuation pipeline.

### Flutter Compatibility Layer (`/api/v1`)
The current Flutter Android client utilizes the `/api/v1` route prefix. The backend provides transparent compatibility:
* `POST /api/v1/ai/detect`: Accepts multipart `file` form upload, executes `/analyze`, returns Flutter presentation JSON.
* `GET /api/v1/devices/{id}/status`: Returns device status in Flutter-compatible structure.
* `POST /api/v1/spray/manual`: Dispatches manual spray subject to `ActuatorAuthorizationService`.
* `POST /api/v1/spray/stop`: Immediate actuator stop fail-safe.
* `POST /api/v1/spray/emergency-stop`: Immediate emergency kill-switch.
* `POST /api/v1/spray/reset-emergency-stop`: Clears emergency lock.
* `GET /api/v1/spray/history`: Retrieves spray history list for Flutter UI.
* `WS /api/v1/ws/{device_id}`: WebSocket streaming live telemetry frames.

---

## 5. Actuator Safety Gate (`ActuatorAuthorizationService`)

**Critical Safety Policy:**
1. **AI is diagnostic only:** Person 1 AI models never directly actuate hardware.
2. **GenAI is explanatory only:** Explainer models cannot control hardware.
3. **Single Authoritative Gate:** `ActuatorAuthorizationService` is the **only** code path authorizing `SPRAY` or `IRRIGATE`.
   * Verifies decision exists and matches the device's field.
   * Verifies decision has not expired (`expires_at > utc_now()`).
   * Verifies `requires_confirmation == false`.
   * Verifies requested action is compatible with `primary_decision` (e.g. spray is blocked if decision is `DELAY_SPRAY` or `MONITOR`).
4. **Independent Fail-Safes:** `STOP` and `EMERGENCY_STOP` **bypass** decision authorization to guarantee instantaneous safety shutdown.

---

## 6. Deterministic Demo Scenarios

Select a scenario by passing the header `X-Demo-Scenario: <NAME>` or query parameter `demo_scenario=<NAME>`:

| Scenario Name | Simulated Conditions | Decision Engine Output | Actuator Result |
| :--- | :--- | :--- | :--- |
| **`TOMATO_EARLY_BLIGHT`** | Early Blight detected, calm weather (rain prob 10%) | `primary_decision = SPRAY`<br>`risk_level = MEDIUM` | **`SPRAY`** authorized (**`SIMULATED`**) |
| **`DISEASE_HEAVY_RAIN`** | Early Blight detected, incoming storm (rain prob 85%, 12mm) | `primary_decision = DELAY_SPRAY`<br>`risk_level = HIGH` | **Spray Inhibited** (**`DELAYED`**) |
| **`HEALTHY`** | Vigorous foliage, zero pathogen pressure | `primary_decision = MONITOR`<br>`risk_level = LOW` | **No Action** (**`INHIBITED`**) |
| **`LOW_MOISTURE_HEAT`** | Soil moisture 14%, ambient temperature 36°C | `primary_decision = IRRIGATE`<br>`risk_level = HIGH` | **`IRRIGATE`** authorized (**`SIMULATED`**) |
| **`LOW_CONFIDENCE`** | Low diagnostic confidence (48%), ambiguous symptom | `primary_decision = WARN`<br>`requires_confirmation = true` | **Spray Blocked** (**`WARNING`**) |

---

## 7. Testing

Run the 23 dedicated Person 4 prototype integration tests:
```powershell
cd backend
pytest tests/test_prototype_integration.py -v
```
All 23 tests validate field management, telemetry ingestion, demo scenarios, safety gates, failure handling, and Flutter `/api/v1` routes.
