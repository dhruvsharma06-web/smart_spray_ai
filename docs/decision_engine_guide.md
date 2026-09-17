# Person 3 Decision Engine Documentation

## 1. Overview & Purpose
The **Decision Engine (Person 3)** translates AI field analysis diagnostics (Person 1) and environmental telemetry into safe, deterministic operational action recommendations for execution by hardware/actuators (Person 2) and integration by Person 4/5.

**Core Philosophy**:
- **Person 1**: Provides AI analysis.
- **Person 3**: Decides **WHAT SHOULD HAPPEN**.
- **Person 2**: Controls **HOW HARDWARE EXECUTES IT**.
- **Person 4**: Integrates backend APIs.
- **Person 5**: Renders UI/visuals.

GenAI models explain diagnostics to farmers but **NEVER** directly actuate hardware or control pumps.

---

## 2. Input & Output Contracts

### Input Contract
`evaluate_decision()` accepts:
- `field_analysis`: `FieldAnalysisOutput` Pydantic object or equivalent dictionary payload from `POST /ai/analyze`.
- `sensor_data`: Soil and ambient environmental readings (`moisture_percent`, `temperature_celsius`, `humidity_percent`, etc.).
- `weather_data`: Meteorological forecast data (`upcoming_24h_rainfall_mm`, etc.).
- `crop_stage`: Crop growth stage (e.g., `"vegetative"`, `"flowering"`, `"fruiting"`).

### Output Contract (`DecisionResult`)
```json
{
  "action": "SPRAY | IRRIGATE | WARN | DELAY | NO_ACTION",
  "reason": "Human-readable operational rationale",
  "priority": "LOW | MEDIUM | HIGH | CRITICAL",
  "requires_confirmation": true,
  "safety_status": "FIELD_HEALTHY | SAFE_TO_SPRAY | SAFE_TO_IRRIGATE | WEATHER_DELAY | CONFIRMATION_REQUIRED | NO_VERIFIED_TREATMENT | CLIMATE_HAZARD | SAFETY_BLOCK | TELEMETRY_INVALID | TELEMETRY_MISSING",
  "duration_minutes": 30.0,
  "verified_treatment": {
    "product": "Mancozeb 75% WP (SAMPLE)",
    "active_ingredient": "Mancozeb",
    "label_rate": "2.5 g/L of water",
    "pre_harvest_interval_days": 7
  },
  "audit": {
    "triggered_rules": ["RULE_RECOMMEND_SPRAY"],
    "inputs_considered": { ... },
    "timestamp": "2026-09-16T01:00:00Z"
  }
}
```

---

## 3. Rule Precedence & Hierarchy

The engine evaluates rules in a strict, deterministic precedence order:

1. **Safety Layer Override Check**:
   - Out-of-bounds telemetry (e.g. soil moisture $< 0\%$ or $> 100\%$) $\rightarrow$ `WARN` (`TELEMETRY_INVALID`, `CRITICAL`)
   - Missing/malformed AI output $\rightarrow$ `WARN` (`SAFETY_BLOCK`, `CRITICAL`)
   - Critical climate hazard (e.g., flood/waterlogging risk $\ge 0.80$) $\rightarrow$ `WARN` (`CLIMATE_HAZARD`, `CRITICAL`)
   - Contradictory telemetry $\rightarrow$ `WARN` (`SAFETY_BLOCK`, `HIGH`)

2. **Confirmation Required / Low Confidence Check**:
   - If AI confidence $< 0.60$ or `requires_confirmation = True` $\rightarrow$ `WARN` (`CONFIRMATION_REQUIRED`, `HIGH`)

3. **Disease / Pest Treatment Evaluation**:
   - If disease/pest present:
     - No verified treatment record in RAG $\rightarrow$ `WARN` (`NO_VERIFIED_TREATMENT`, `HIGH`)
     - Verified treatment available BUT heavy rain ($\ge 15.0$mm/24h) or flood/waterlogging risk $\ge 0.50$ $\rightarrow$ `DELAY` (`WEATHER_DELAY`, `HIGH`/`MEDIUM`)
     - Verified treatment available AND weather suitable $\rightarrow$ `SPRAY` (`SAFE_TO_SPRAY`, `HIGH`/`MEDIUM`)

4. **Irrigation Evaluation**:
   - If soil moisture $< 25.0\%$ or drought risk $\ge 0.50$ (and soil not saturated $\ge 80\%$, flood $< 0.50$) $\rightarrow$ `IRRIGATE` (`SAFE_TO_IRRIGATE`, `HIGH`/`MEDIUM`)

5. **Default / Healthy Field**:
   - No disease, no pest, optimal soil moisture & low climate risks $\rightarrow$ `NO_ACTION` (`FIELD_HEALTHY`, `LOW`)

---

## 4. Five Demo Scenarios

| Scenario | Inputs | Outcome | Priority | Safety Status |
|---|---|---|---|---|
| **Scenario 1** | Tomato Early Blight + High Conf + Verified Treatment (Mancozeb) + Suitable Weather | `SPRAY` | `HIGH` | `SAFE_TO_SPRAY` |
| **Scenario 2** | Tomato Early Blight + Verified Treatment + Heavy Rain Forecast (25mm) | `DELAY` | `HIGH` | `WEATHER_DELAY` |
| **Scenario 3** | Healthy Crop + Normal Soil Moisture (45%) + Low Climate Risk | `NO_ACTION` | `LOW` | `FIELD_HEALTHY` |
| **Scenario 4** | Low Soil Moisture (15%) + High Drought Risk (0.75) + Safe Conditions | `IRRIGATE` | `HIGH` | `SAFE_TO_IRRIGATE` |
| **Scenario 5** | Low Confidence AI Diagnosis (45%) | `WARN` | `HIGH` | `CONFIRMATION_REQUIRED` |

---

## 5. Integration Contract
Exposed via Python import:
```python
from ai.decision import evaluate_decision, DecisionEngine

result = evaluate_decision(
    field_analysis=field_analysis_output,
    sensor_data=sensor_data_dict,
    weather_data=weather_data_dict,
    crop_stage="vegetative"
)
```
And HTTP API endpoint:
`POST /ai/decision`
