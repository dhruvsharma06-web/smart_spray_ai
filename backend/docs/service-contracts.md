# Smart Spray AI — Service Contracts

Version: 1.0  
Last Updated: 2026-09-16  
Status: Frozen (Real Service Integration Phase 1)

This document specifies the exact, frozen JSON and HTTP contracts between the Smart Spray Backend and all external services (AI Service, Decision Engine, and GenAI Assistant).

---

## 1. Backend → AI Service Request

### Endpoint
```http
POST {AI_SERVICE_URL}/ai/analyze
```
- Configured via environment variable: `AI_SERVICE_URL` (default: `http://mock-ai:8001`).
- Protocol: HTTP/1.1 or HTTP/2.
- Content-Type: `multipart/form-data`.

### Request Parameters (multipart/form-data)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `image` | binary file | **Yes** | Foliage image file (JPEG, PNG, WEBP). Enforced max size: `MAX_IMAGE_BYTES` (default 10 MB). |
| `sensor_data` | string (JSON) | **Yes** | Serialized JSON string of latest IoT sensor telemetry. Pass `"{}"` if unavailable. |
| `weather_data` | string (JSON) | **Yes** | Serialized JSON string of ambient weather and forecasts. Pass `"{}"` if unavailable. |
| `crop_stage` | string | No | Growth stage name (e.g. `"vegetative"`, `"flowering"`, `"fruiting"`). Default: `""`. |

#### `sensor_data` JSON Structure
```json
{
  "soil": {
    "moisture_percent": 45.0,
    "temperature_celsius": 24.5
  },
  "air": {
    "temperature_celsius": 28.0,
    "humidity_percent": 65.0
  },
  "tank_level": 80.0,
  "pump": false
}
```

#### `weather_data` JSON Structure
```json
{
  "temperature": 28.0,
  "humidity": 65.0,
  "rainfall": 0.0,
  "rain_probability": 15.0,
  "forecast": [
    {
      "hours": 24,
      "rain_probability": 20.0
    }
  ],
  "extreme_weather": []
}
```

### Timeouts & Resilience
- **Connect Timeout**: 10.0 seconds.
- **Read / Inference Timeout**: 120.0 seconds (accommodates GPU/CPU model inference pipelines).
- **Retries**: 3 attempts with exponential backoff (base delay: 1.0s, max delay: 10.0s).

### Authentication
- Internal Docker bridge network / microservice mesh: No auth header required by default.
- External / Cloud deployment: `Authorization: Bearer <AI_SERVICE_TOKEN>` (optional header supported by client).

---

## 2. AI Service → Backend Response

### Response Format
- Status: `200 OK`
- Content-Type: `application/json`

### JSON Payload Schema
```json
{
  "crop": {
    "name": "tomato",
    "confidence": 0.96,
    "scientific_name": "Solanum lycopersicum",
    "confidence_level": "high"
  },
  "disease": {
    "name": "early_blight",
    "confidence": 0.94,
    "severity": "moderate",
    "affected_area_percent": 18.5,
    "display_name": "Early Blight",
    "is_healthy": false,
    "symptoms": ["concentric_rings", "dark_spots"],
    "detections": []
  },
  "pests": [
    {
      "name": "aphid",
      "confidence": 0.88,
      "count": 5,
      "bounding_box": {
        "ymin": 0.12,
        "xmin": 0.34,
        "ymax": 0.25,
        "xmax": 0.48
      },
      "detections": null
    }
  ],
  "nutrient_deficiency": null,
  "severity": {
    "level": "moderate",
    "affected_area_percent": 18.5,
    "confidence": 0.90,
    "progression_risk": "medium"
  },
  "climate_risk": {
    "drought": 0.20,
    "heat": 0.35,
    "flood": 0.05,
    "waterlogging": 0.10
  },
  "requires_confirmation": false,
  "recommendations": [
    "Apply copper-based fungicide to infected foliage",
    "Ensure adequate soil drainage"
  ],
  "metadata": {
    "model_version": "v1.0.0"
  }
}
```

### Strict Validation Rules (Pydantic Schema)
1. **`crop` (Required Object)**:
   - `name`: Non-empty string (`min_length=1`). Also accepts `crop_name` as alias.
   - `confidence`: Float strictly bounded between `0.0` and `1.0`.
   - `scientific_name`: Optional string.
   - `confidence_level`: Optional string (`"high"`, `"moderate"`, `"low"`).
2. **`disease` (Optional Object or `null`)**:
   - `name`: Optional string. Non-empty string or `null`. Also accepts `disease` as alias.
   - `confidence`: Optional float strictly bounded between `0.0` and `1.0`.
   - `severity`: Optional string (`"healthy"`, `"low"`, `"moderate"`, `"high"`, `"critical"`).
   - `affected_area_percent`: Optional float strictly bounded between `0.0` and `100.0`.
   - `display_name`: Optional string.
   - `is_healthy`: Optional boolean.
   - `detections`: Optional list of bounding boxes / detection dictionaries.
3. **`pests` (List of Objects, default `[]`)**:
   - Each pest object MUST contain:
     - `name`: Non-empty string (`min_length=1`). Also accepts `pest_type` as alias.
     - `confidence`: Float strictly bounded between `0.0` and `1.0`.
   - Optional pest fields:
     - `count`: Optional integer `>= 0`.
     - `bounding_box`: Optional object with normalized coordinates (`ymin`, `xmin`, `ymax`, `xmax`), all floats `0.0` to `1.0`.
     - `detections`: Optional dictionary or list.
4. **`nutrient_deficiency` (Optional Object, String, or `null`)**:
   - Accepts string (e.g. `"nitrogen"`), dictionary of nutrient indices, or `null`.
5. **`severity` (Optional Object or `null`)**:
   - `level`: Optional string.
   - `affected_area_percent`: Optional float strictly `0.0` to `100.0`.
   - `confidence`: Optional float `0.0` to `1.0`.
   - `progression_risk`: Optional string.
6. **`climate_risk` (Required Object)**:
   - `drought`: Float strictly `0.0` to `1.0`.
   - `heat`: Float strictly `0.0` to `1.0`.
   - `flood`: Float strictly `0.0` to `1.0`.
   - `waterlogging`: Float strictly `0.0` to `1.0`.
7. **`requires_confirmation` (Boolean, default `false`)**:
   - Flag indicating whether low confidence or ambiguous symptoms require human confirmation before action.
8. **`recommendations` (Optional List of Strings)**:
   - Optional list of recommended treatments or cultural actions.
9. **Forward Compatibility**:
   - Extra fields in the AI response are preserved in raw storage and ignored during model mapping without validation errors (`extra = 'allow'`).

---

## 3. Backend → Decision Engine Request

### Endpoints
```http
GET {DECISION_SERVICE_URL}/health
POST {DECISION_SERVICE_URL}/decision
```
- Configured via environment variable: `DECISION_SERVICE_URL` (standalone service: `http://decision:8002`, mock fallback: `http://mock-decision:8002`).
- Service Host / Port: `0.0.0.0:8002` (internal Docker network: `http://decision:8002`, host mapped: `8002:8002`).
- Content-Type: `application/json`.

### Health Check Endpoint
```http
GET /health
```
**Response (200 OK):**
```json
{
  "status": "ok",
  "service": "decision-engine"
}
```

### Decision Evaluation Endpoint
```http
POST /decision
```

### Request Body (application/json)
```json
{
  "analysis": {
    "crop": { "name": "tomato", "confidence": 0.96 },
    "disease": { "name": "early_blight", "confidence": 0.94 },
    "pests": [],
    "nutrient_deficiency": null,
    "severity": { "level": "moderate", "affected_area_percent": 18.5 },
    "climate_risk": { "drought": 0.2, "heat": 0.35, "flood": 0.05, "waterlogging": 0.1 },
    "requires_confirmation": false
  },
  "sensor_data": {
    "soil": { "moisture_percent": 45.0 },
    "air": { "temperature_celsius": 28.0 }
  },
  "weather_data": {
    "rain_probability": 15.0,
    "temperature": 28.0
  },
  "field_id": 42
}
```

### Timeouts & Resilience
- **Connect Timeout**: 5.0 seconds.
- **Read Timeout**: 30.0 seconds.
- **Retries**: 3 attempts with exponential backoff (base delay: 0.5s, max delay: 5.0s).

---

## 4. Decision Engine → Backend Response

### Response Format
- Status: `200 OK`
- Content-Type: `application/json`

### Frozen JSON Payload Schema
```json
{
  "primary_decision": "SPRAY",
  "risk_level": "MEDIUM",
  "actions": [
    {
      "type": "SPRAY",
      "priority": "MEDIUM"
    }
  ],
  "warnings": [],
  "requires_confirmation": false
}
```

### Strict Enum Validation
1. **`primary_decision`**:
   - `SPRAY`: Foliar pesticide or fungicide application recommended.
   - `IRRIGATE`: Irrigation pump activation recommended due to low soil moisture or drought risk.
   - `DELAY_SPRAY`: Spray delayed due to incoming rainfall ($\ge 70\%$) or extreme heat ($\ge 38^\circ\text{C}$).
   - `MONITOR`: Crops healthy, no interventions required; routine monitoring continues.
   - `WARN`: Agronomic condition requires attention (e.g. nutrient deficiency or moderate heat).
2. **`risk_level`**:
   - `LOW` | `MEDIUM` | `HIGH` | `CRITICAL`.
3. **`actions`**: List of actionable recommendations:
   - `type`: `SPRAY` | `IRRIGATION` | `IRRIGATE` | `DELAY_SPRAY` | `MONITOR` | `WARN`.
   - `priority`: `LOW` | `MEDIUM` | `HIGH`.
4. **`warnings`**: List of human-readable diagnostic strings (e.g. rain wash-off warnings, heat scorch alerts, low confidence notices).
5. **`requires_confirmation`**: Boolean. When `true`, indicates low model confidence (< 0.60) or ambiguous conditions; the backend blocks actuation until a human operator confirms.

### Error Behavior
- **Invalid Request Input**: Decision Engine returns `422 Unprocessable Entity` when input cannot be parsed.
- **Evaluation Failure**: Decision Engine returns `500 Internal Server Error` on unhandled rule engine exceptions.
- **Backend Error Handling**: Backend translates Decision Engine connection failures, timeouts, 5xx errors, or Pydantic validation mismatches into `502 Bad Gateway`. Actuators are never commanded on decision failures.

### Safety Boundary & Service Ownership
- **Actuator Execution Boundary**: The Decision Engine recommendation is strictly an advisory payload and does NOT constitute permission or command authority to activate physical hardware.
- **Backend Enforcement**: Device actuation requires:
  1. Valid, non-expired Decision persisted in PostgreSQL with `expires_at > NOW()`.
  2. Action type strictly matching `primary_decision` (e.g., `SPRAY` for spray valve, `IRRIGATE` for irrigation pump).
  3. Server-side safety verification (`validate_command`) checking online status and tank level.
- **Emergency STOP Independence**: Emergency `stop` commands are always permitted immediately, regardless of decision status or expiration.
- **Architectural Isolation**: Neither the AI Service nor the Decision Engine has network access to the ESP32 hardware or MQTT/command bus. All device control is strictly brokered by the Backend IoT subsystem.
- **Service Ownership**:
  - `ai`: Image diagnostics and symptom detection (`POST /ai/analyze`).
  - `decision`: Deterministic agronomic policy and decision generation (`POST /decision`).
  - `backend`: Persistence, authentication, authorization, decision expiry, and hardware safety governance.
  - `genai`: Farmer-facing natural language explanations (`POST /assistant/explain`).

---

## 5. Backend → GenAI Service Request

### Endpoint
```http
POST {GENAI_SERVICE_URL}/assistant/explain
```
- Configured via environment variable: `GENAI_SERVICE_URL` (default: `http://mock-genai:8003`).
- Content-Type: `application/json`.

### Request Body (application/json)
```json
{
  "analysis": { /* full AI AnalysisResult object */ },
  "decision": { /* full DecisionResult object */ }
}
```

### Timeouts & Resilience
- **Connect Timeout**: 5.0 seconds.
- **Read Timeout**: 60.0 seconds.
- **Retries**: 2 attempts with exponential backoff.
- **Resilience Policy**: Non-blocking. If GenAI fails, times out, or returns HTTP 4xx/5xx, the backend silently falls back to local template explanation.

---

## 6. GenAI Service → Backend Response

### Response Format
- Status: `200 OK`
- Content-Type: `application/json`

```json
{
  "text": "The system identified tomato. Possible early blight was detected. Recommended action: spray.",
  "source": "mock-genai"
}
```

### Backend Fallback Guarantee
If GenAI is unreachable, Backend produces:
`"The system identified {crop}. Possible {disease} was detected. Recommended action: {decision}."` with `"source": "fallback"`.

---

## 7. Backend API Client Schema: POST /api/analysis

### Endpoint
```http
POST /api/analysis
```
- Headers: `Authorization: Bearer <JWT_TOKEN>`
- Content-Type: `multipart/form-data`

### Form Fields
- `field_id`: integer (Form data, required)
- `image`: binary file (File data, required, image/* content-type, max 10MB)

### Success Response (200 OK)
```json
{
  "analysis_id": 101,
  "analysis": { /* validated AI response */ },
  "decision": { /* validated Decision Engine response */ },
  "weather": { /* weather snapshot */ }
}
```

---

## 8. Error Formats & Mapping

| Scenario | Service Behavior | Backend Response to Frontend |
|----------|------------------|------------------------------|
| AI Timeout | Client retries 3x, raises `TimeoutException` | `502 Bad Gateway` (`{"detail": "Analysis service unavailable or failed"}`) |
| AI HTTP 4xx | Client raises `HTTPStatusError` | `502 Bad Gateway` (`{"detail": "Analysis service unavailable or failed"}`) |
| AI HTTP 5xx | Client retries 3x, raises `HTTPStatusError` | `502 Bad Gateway` (`{"detail": "Analysis service unavailable or failed"}`) |
| AI Unavailable | Client retries 3x, raises `ConnectError` | `502 Bad Gateway` (`{"detail": "Analysis service unavailable or failed"}`) |
| Malformed AI Response | Fails strict Pydantic validation | `502 Bad Gateway` (`{"detail": "AI response validation failed: ..."}` or `502`) |
| Invalid Upload Type | Content-type does not start with `image/` | `415 Unsupported Media Type` (`{"detail": "Only image uploads are accepted"}`) |
| Oversized Image | Upload exceeds `MAX_IMAGE_BYTES` | `413 Payload Too Large` (`{"detail": "Image too large"}`) |
| Unauthorized / Wrong Owner | Missing JWT or field not owned | `401 Unauthorized` / `403 Forbidden` / `404 Not Found` |

### Safety Guarantee
**Whenever AI analysis fails or validation is rejected:**
1. No `AIAnalysis` entity is persisted in the database (transaction is rolled back).
2. The Decision Engine is NEVER called.
3. No `Decision` record is created.
4. No actuator action (`SprayEvent`) can be authorized or triggered.

---

## 9. Environment Configuration

| Variable | Default Value | Description |
|----------|---------------|-------------|
| `AI_SERVICE_URL` | `http://mock-ai:8001` | Base URL of the AI Microservice |
| `DECISION_SERVICE_URL` | `http://mock-decision:8002` | Base URL of the Decision Engine |
| `GENAI_SERVICE_URL` | `http://mock-genai:8003` | Base URL of the GenAI Assistant |
| `MAX_IMAGE_BYTES` | `10485760` (10 MB) | Maximum upload size allowed for foliage images |
| `DECISION_TTL_SECONDS` | `300` (5 min) | Time before an approved decision expires |
| `WEATHER_PROVIDER` | `mock` | Weather provider engine (`mock` or real API) |

---

## 10. Versioning Expectations

- **Additive Changes**: New optional fields in responses (e.g. `symptoms`, `recommendations`, `metadata`) are backward compatible and do not bump the API contract version.
- **Breaking Changes**: Changing field names (e.g. removing `crop` or `confidence`), modifying value ranges, or adding new mandatory request fields require a major version bump (`/v2/`).
- **Contract Freeze**: Any future real AI service implementation must adhere strictly to this schema contract.
