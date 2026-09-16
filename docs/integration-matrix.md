# Smart Spray AI — Repository-Wide Integration Matrix

**Status**: Read-Only Architectural Audit  
**Date**: 2026-09-16  
**Audited Branches**: `backend` (FastAPI + PostgreSQL + Hardened Security) vs `master` (Person 1 AI/ML Core + External Components)

---

## 1. Executive Summary

A comprehensive repository audit was performed across the `backend` branch, `master` branch, and related filesystem components.

### Key Discoveries:
1. **Master Branch State**:
   - Contains **Person 1's complete AI/ML + GenAI Core** (`ai/`), complete with FastAPI service (`ai/api.py`), 8-stage analysis pipeline (`ai/inference/analyze_field.py`), multimodal crop vision, YOLO disease/pest detection, visual nutrient assessment, climate risk evaluation, RAG treatment database, and farmer GenAI explanation.
   - Commit `cacc7b9` titled `"feat: add decision engine and flutter frontend"` only deleted `.pyc` cache files; no Flutter or Decision Engine code was committed to git in `master`.
   - The Flutter frontend and initial prototype logic exist in the project tree (`C:\dev\SmartSpray`), containing the Flutter client (`flutter_app/`) and prototype hardware controller.
2. **Backend Branch State**:
   - Hardened FastAPI enterprise backend with 193 passing tests, PostgreSQL integration, JWT authentication, farm/field/device tenancy, sensor history, decision TTL expiry, device safety boundaries, and idempotent command dispatch.
   - External services are decoupled via resilient HTTP adapters (`AIService`, `DecisionService`, `GenAIService`).

---

## 2. Contract Compatibility Matrix

| Component Flow | Existing Master / Prototype Contract | Hardened Backend Contract | Compatible? | Required Changes |
|---|---|---|---|---|
| **Flutter → Backend (Auth)** | None (no authentication headers used in Flutter). | `Authorization: Bearer <JWT>` required on all protected endpoints. | ❌ **No** | Add authentication service / token interceptor in Flutter `ApiService`. |
| **Flutter → Backend (Analysis)** | `POST /api/v1/ai/detect` (multipart `file` only, unwrapped `data`). | `POST /api/analysis` (multipart `image` + form field `field_id`). | ❌ **No** | Point Flutter `AiRepository` to `POST /api/analysis`, attach active `field_id`, and handle `{analysis_id, analysis, decision, weather}` payload. |
| **Flutter → Backend (Spray / Control)** | `POST /api/v1/spray/manual` with `{device_id, duration_ms, command_id}` (No decision needed). | `POST /api/devices/{device_id}/spray?decision_id={id}` (Strict decision check). | ❌ **No** | Update Flutter `SprayRepository` to pass `decision_id`. Disallow unverified manual sprays without active valid decisions. |
| **Backend → AI Request** | `POST /ai/analyze` (multipart: `image`, `sensor_data`, `weather_data`, `crop_stage`). | `POST /ai/analyze` (multipart: `image`, `sensor_data`, `weather_data`, `crop_stage`). | ✅ **Yes** | Fully compatible. Backend `AIService` matches `ai/api.py` endpoint and parameters. |
| **AI → Backend Response** | `FieldAnalysisOutput` (`crop`, `disease`, `pests`, `nutrient_deficiency`, `severity`, `climate_risk`, `requires_confirmation`, `metadata`). | `AnalysisResult` Pydantic model with normalized aliases (`pest_type`, `crop_name`, `disease`, bounding boxes). | ✅ **Yes** | Fully compatible. Backend Pydantic schema accepts `FieldAnalysisOutput` with 100% field alignment. |
| **Backend → Decision Engine** | Inline prototype function `determine_spray_action` in `pipeline.py`. | HTTP `POST /decision` with `{analysis, sensor_data, weather_data, field_id}`. | ⚠️ **Partial** | Wrap decision rules into standalone HTTP microservice or importable engine implementing the frozen `POST /decision` contract. |
| **Decision Engine → Backend** | Returns `{"recommendation": str, "reason": str, "auto_permitted": bool}`. | Returns `{"primary_decision": str, "risk_level": str, "actions": list, "warnings": list, "requires_confirmation": bool}`. | ❌ **No** | Standardize Decision Engine output to match frozen contract (`primary_decision` enum: `SPRAY`, `IRRIGATE`, `DELAY_SPRAY`, `MONITOR`, `WARN`). |
| **Backend → GenAI** | `ai/genai/explainer.py` (`ExplanationInput` -> `GenAIExplainer`). | `POST /assistant/explain` with `{analysis, decision}` (with automatic fallback). | ⚠️ **Partial** | Expose GenAI explainer via HTTP endpoint `POST /assistant/explain` or invoke via AI pipeline metadata. |
| **Backend → IoT / Device** | Prototype direct serial write (`hardware_controller.py`). | `POST /api/sensors/telemetry` (ingestion) and validated command state machine. | ✅ **Yes** | IoT devices communicate via HTTP telemetry and command polling/webhooks. |

---

## 3. Duplication Analysis

| Functional Area | Master / Prototype Implementation | Backend Branch Implementation | Authoritative Component | Rationale |
|---|---|---|---|---|
| **Decision Logic** | `determine_spray_action()` in `pipeline.py` (heuristic based only on severity level). | `DecisionService` (`/decision`) + `validate_command` (weather rain delay, drought irrigation, TTL expiry, confirmation). | **Backend Branch & Decision Engine** | Decision logic must consider agronomic weather forecasts, soil sensors, chemical labels, and expiry, not just leaf vision. |
| **Safety Validation** | Client-side and basic controller checks. | Adversarial safety boundary (`validate_command`, offline checks, tank level, ownership). | **Backend Branch** | Actuators must be strictly guarded behind server-side safety boundaries. |
| **Image Processing** | `ImageLoader` in `ai/inference/image_loader.py` (PIL, Base64, OpenCV). | `ImageStorage` in `app/services/storage.py` (filesystem persistence). | **Hybrid** | Backend persists raw uploads to disk/storage abstraction; AI service reads image bytes using `ImageLoader`. |
| **Authentication & Tenancy** | None. | JWT auth, password hashing, multi-tenant farm/field isolation. | **Backend Branch** | Critical for multi-user security and farm data isolation. |
| **Device Control** | Serial manager in `hardware_controller.py`. | REST telemetry endpoints, status tracking, idempotency keys, command dispatch. | **Backend Branch** | Production-ready IoT devices report telemetry over network rather than local PC COM ports. |
| **GenAI Explanations** | `ai/genai/explainer.py` (Gemini Flash + Mock fallback + RAG). | `app/genai/client.py` (HTTP client with offline template fallback). | **Master AI Module (`ai/genai`)** | Master contains full RAG knowledge base and Gemini prompts. Backend acts as resilient consumer. |

---

## 4. Critical Safety Boundary Verification

### Intended Architecture:
```
Flutter Frontend
       │ (1. Upload image + telemetry)
       ▼
Backend API (/api/analysis)
       │ (2. Forward payload)
       ▼
AI Microservice (/ai/analyze)
       │ (3. Diagnostic results & risks)
       ▼
Decision Engine (/decision)
       │ (4. Agronomic recommendation & TTL)
       ▼
Backend Safety Validator (validate_command)
       │ (5. Verify ownership, decision validity, tank level, device status)
       ▼
IoT / Actuator Device
       │ (6. Dispatched command)
       ▼
Pump / Spray Valve
```

### Safety Audit Finding:
- **Master / Prototype**: **VIOLATED**. The Flutter client contained direct calls to `POST /spray/manual`, allowing an arbitrary user or UI script to trigger pump actuation for arbitrary durations without diagnostic justification, decision authorization, or tank verification.
- **Backend Branch**: **ENFORCED**. Direct actuation without an active, non-expired, matching decision returns HTTP 400/404/422. Emergency stop (`/stop`) remains unrestricted for immediate safety shutdown.

---

## 5. Flutter Migration Requirements

To integrate the Flutter frontend with the hardened backend, the following modifications are required:

| Current Flutter Call | Target Backend Call | Affected Flutter Files |
|---|---|---|
| `POST /ai/detect` (multipart file only) | `POST /api/analysis` (multipart `image`, form `field_id`, Bearer token) | `lib/repositories/ai_repository.dart`<br>`lib/features/detection/detection_provider.dart` |
| `POST /spray/manual` (`device_id`, `duration_ms`) | `POST /api/devices/{id}/spray?decision_id={decision_id}` | `lib/repositories/spray_repository.dart`<br>`lib/features/control/control_provider.dart` |
| `GET /devices/{id}/status` | `GET /api/devices/{id}` | `lib/repositories/device_repository.dart` |
| Direct HTTP calls without auth | Attach `Authorization: Bearer <token>` | `lib/services/api_service.dart`<br>`lib/core/config/api_config.dart` |
| Missing user login/registration | Implement auth login/token storage | `lib/features/auth/` (New feature module) |

---

## 6. Recommended Runtime Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Docker Network                         │
│                                                             │
│  ┌────────────────┐     ┌────────────────┐                  │
│  │   PostgreSQL   │◄────┤  FastAPI Core  │◄─── Flutter / UI │
│  │   (Port 5432)  │     │  (Port 8000)   │                  │
│  └────────────────┘     └───────┬────────┘                  │
│                                 │                           │
│             ┌───────────────────┼───────────────────┐       │
│             │                   │                   │       │
│             ▼                   ▼                   ▼       │
│     ┌───────────────┐   ┌───────────────┐   ┌─────────────┐ │
│     │ AI Service    │   │Decision Engine│   │GenAI Service│ │
│     │ (ai.api:8001) │   │  (Port 8002)  │   │ (Port 8003) │ │
│     └───────────────┘   └───────────────┘   └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

1. **AI Service**: Runs `ai/api.py` natively via `uvicorn ai.api:app --port 8001`. Already implemented and test-verified.
2. **Decision Engine**: Standalone lightweight microservice running the agronomic decision matrix (weather rain-delay, drought irrigate, severity spray, expiry).
3. **Backend Core**: Orchestrator, Auth, DB models, Device Safety Boundary, and IoT ingestion.
