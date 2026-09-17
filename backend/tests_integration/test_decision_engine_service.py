import pytest
import httpx
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from pydantic import ValidationError
from app.decision.client import DecisionService
from app.schemas.decision_response import DecisionResponseOut, PrimaryDecision, RiskLevel, ActionType, Priority
from app.config import settings


class TestDecisionEngineService:
    """Comprehensive test suite for the standalone Decision Engine service."""

    # 1. Health endpoint
    @pytest.mark.asyncio
    async def test_01_decision_health_endpoint(self, real_decision_client):
        r = await real_decision_client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["service"] == "decision-engine"

    # 2. Valid decision request
    @pytest.mark.asyncio
    async def test_02_valid_decision_request(self, real_decision_client):
        payload = {
            "analysis": {
                "crop": {"name": "tomato", "confidence": 0.95},
                "disease": {"name": "healthy", "confidence": 0.9},
                "climate_risk": {"drought": 0.1, "heat": 0.1, "flood": 0.0, "waterlogging": 0.0},
            },
            "sensor_data": {"soil": {"moisture_percent": 45.0}},
            "weather_data": {"rain_probability": 10.0, "temperature": 24.0},
        }
        r = await real_decision_client.post("/decision", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert "primary_decision" in data
        assert "risk_level" in data
        assert "actions" in data
        assert "warnings" in data
        assert "requires_confirmation" in data

    # 3. SPRAY response
    @pytest.mark.asyncio
    async def test_03_spray_response(self, real_decision_client):
        payload = {
            "analysis": {
                "crop": {"name": "tomato", "confidence": 0.95},
                "disease": {"name": "early_blight", "confidence": 0.88, "severity": "moderate"},
                "climate_risk": {"drought": 0.0, "heat": 0.0, "flood": 0.0, "waterlogging": 0.0},
            },
            "sensor_data": {"soil": {"moisture_percent": 50.0}},
            "weather_data": {"rain_probability": 10.0, "temperature": 22.0},
        }
        r = await real_decision_client.post("/decision", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["primary_decision"] == "SPRAY"
        assert len(data["actions"]) > 0
        assert data["actions"][0]["type"] == "SPRAY"

    # 4. IRRIGATE response
    @pytest.mark.asyncio
    async def test_04_irrigate_response(self, real_decision_client):
        payload = {
            "analysis": {
                "crop": {"name": "corn", "confidence": 0.92},
                "climate_risk": {"drought": 0.85, "heat": 0.2, "flood": 0.0, "waterlogging": 0.0},
            },
            "sensor_data": {"soil": {"moisture_percent": 15.0}},
            "weather_data": {"rain_probability": 0.0, "temperature": 28.0},
        }
        r = await real_decision_client.post("/decision", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["primary_decision"] == "IRRIGATE"
        assert data["actions"][0]["type"] in ("IRRIGATION", "IRRIGATE")

    # 5. DELAY_SPRAY response
    @pytest.mark.asyncio
    async def test_05_delay_spray_response(self, real_decision_client):
        payload = {
            "analysis": {
                "crop": {"name": "grape", "confidence": 0.93},
                "disease": {"name": "powdery_mildew", "confidence": 0.85, "severity": "high"},
                "climate_risk": {"drought": 0.0, "heat": 0.0, "flood": 0.2, "waterlogging": 0.1},
            },
            "sensor_data": {},
            "weather_data": {"rain_probability": 85.0, "rainfall": 12.0},
        }
        r = await real_decision_client.post("/decision", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["primary_decision"] == "DELAY_SPRAY"
        assert data["actions"][0]["type"] == "DELAY_SPRAY"

    # 6. MONITOR response
    @pytest.mark.asyncio
    async def test_06_monitor_response(self, real_decision_client):
        payload = {
            "analysis": {
                "crop": {"name": "wheat", "confidence": 0.94},
                "disease": {"name": "healthy", "confidence": 0.95},
                "climate_risk": {"drought": 0.05, "heat": 0.05, "flood": 0.0, "waterlogging": 0.0},
            },
            "sensor_data": {"soil": {"moisture_percent": 55.0}},
            "weather_data": {"rain_probability": 5.0, "temperature": 21.0},
        }
        r = await real_decision_client.post("/decision", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["primary_decision"] == "MONITOR"
        assert data["risk_level"] == "LOW"

    # 7. WARN response
    @pytest.mark.asyncio
    async def test_07_warn_response(self, real_decision_client):
        payload = {
            "analysis": {
                "crop": {"name": "soybean", "confidence": 0.91},
                "nutrient_deficiency": {"primary_deficiency": "nitrogen"},
                "climate_risk": {"drought": 0.1, "heat": 0.1, "flood": 0.0, "waterlogging": 0.0},
            },
            "sensor_data": {"soil": {"moisture_percent": 40.0}},
            "weather_data": {"rain_probability": 10.0, "temperature": 25.0},
        }
        r = await real_decision_client.post("/decision", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["primary_decision"] == "WARN"

    # 8. Risk levels
    @pytest.mark.asyncio
    async def test_08_risk_levels(self, real_decision_client):
        # High severity disease -> HIGH risk
        high_payload = {
            "analysis": {
                "crop": {"name": "potato", "confidence": 0.9},
                "disease": {"name": "late_blight", "confidence": 0.9, "severity": "high"},
                "climate_risk": {},
            },
            "weather_data": {},
        }
        r1 = await real_decision_client.post("/decision", json=high_payload)
        assert r1.status_code == 200
        assert r1.json()["risk_level"] == "HIGH"

        # Moderate disease -> MEDIUM risk
        med_payload = {
            "analysis": {
                "crop": {"name": "potato", "confidence": 0.9},
                "disease": {"name": "early_blight", "confidence": 0.75, "severity": "moderate"},
                "climate_risk": {},
            },
            "weather_data": {},
        }
        r2 = await real_decision_client.post("/decision", json=med_payload)
        assert r2.status_code == 200
        assert r2.json()["risk_level"] == "MEDIUM"

        # Healthy crop -> LOW risk
        low_payload = {
            "analysis": {
                "crop": {"name": "potato", "confidence": 0.9},
                "disease": {"name": "healthy", "confidence": 0.95},
                "climate_risk": {},
            },
            "weather_data": {},
        }
        r3 = await real_decision_client.post("/decision", json=low_payload)
        assert r3.status_code == 200
        assert r3.json()["risk_level"] == "LOW"

    # 9. Invalid input rejection
    @pytest.mark.asyncio
    async def test_09_invalid_input_rejection(self, real_decision_client):
        # Send non-dict/invalid schema structure
        r = await real_decision_client.post("/decision", json="not a dictionary")
        assert r.status_code == 422

    # 10. Invalid decision response rejection
    def test_10_invalid_decision_response_rejection(self):
        # Test client validation when decision engine returns invalid enum
        invalid_data = {
            "primary_decision": "INVALID_ACTION",
            "risk_level": "LOW",
            "actions": [],
            "warnings": [],
            "requires_confirmation": False,
        }
        with pytest.raises(ValidationError):
            DecisionResponseOut.model_validate(invalid_data)

        invalid_risk = {
            "primary_decision": "SPRAY",
            "risk_level": "EXTREME",  # Invalid enum value
            "actions": [],
            "warnings": [],
            "requires_confirmation": False,
        }
        with pytest.raises(ValidationError):
            DecisionResponseOut.model_validate(invalid_risk)

    # 11. Weather/rain delay behavior
    @pytest.mark.asyncio
    async def test_11_weather_rain_delay_behavior(self, real_decision_client):
        # Even with severe disease present, high rain probability delays spraying
        payload = {
            "analysis": {
                "crop": {"name": "tomato", "confidence": 0.9},
                "disease": {"name": "late_blight", "confidence": 0.92, "severity": "high"},
            },
            "weather_data": {"rain_probability": 75.0, "rainfall": 8.0},
        }
        r = await real_decision_client.post("/decision", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["primary_decision"] == "DELAY_SPRAY"
        assert any("rainfall" in w.lower() or "rain" in w.lower() for w in data["warnings"])

    # 12. Disease severity behavior
    @pytest.mark.asyncio
    async def test_12_disease_severity_behavior(self, real_decision_client):
        # High severity -> priority HIGH
        payload_high = {
            "analysis": {
                "crop": {"name": "rice", "confidence": 0.95},
                "disease": {"name": "blast", "confidence": 0.89, "affected_area_percent": 45.0, "severity": "high"},
            },
            "weather_data": {"rain_probability": 10.0},
        }
        r_high = await real_decision_client.post("/decision", json=payload_high)
        assert r_high.status_code == 200
        assert r_high.json()["actions"][0]["priority"] == "HIGH"

    # 13. Pest severity behavior
    @pytest.mark.asyncio
    async def test_13_pest_severity_behavior(self, real_decision_client):
        # Pest count >= 10 -> high priority spray
        payload = {
            "analysis": {
                "crop": {"name": "cotton", "confidence": 0.92},
                "pests": [{"name": "bollworm", "count": 15, "confidence": 0.85}],
            },
            "weather_data": {"rain_probability": 15.0},
        }
        r = await real_decision_client.post("/decision", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["primary_decision"] == "SPRAY"
        assert data["risk_level"] == "HIGH"
        assert data["actions"][0]["priority"] == "HIGH"

    # 14. Irrigation/drought behavior
    @pytest.mark.asyncio
    async def test_14_irrigation_drought_behavior(self, real_decision_client):
        # Soil moisture under 20% triggers IRRIGATE
        payload = {
            "analysis": {"crop": {"name": "wheat", "confidence": 0.9}},
            "sensor_data": {"soil": {"moisture_percent": 12.0}},
            "weather_data": {"rain_probability": 0.0},
        }
        r = await real_decision_client.post("/decision", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["primary_decision"] == "IRRIGATE"
        assert data["actions"][0]["type"] in ("IRRIGATION", "IRRIGATE")

    # 15. requires_confirmation behavior
    @pytest.mark.asyncio
    async def test_15_requires_confirmation_behavior(self, real_decision_client):
        # Low crop confidence triggers confirmation flag
        payload = {
            "analysis": {
                "crop": {"name": "unknown_plant", "confidence": 0.45},
                "disease": {"name": "leaf_spot", "confidence": 0.50},
            },
            "weather_data": {"rain_probability": 10.0},
        }
        r = await real_decision_client.post("/decision", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["requires_confirmation"] is True
        assert any("confirmation" in w.lower() or "confidence" in w.lower() for w in data["warnings"])

    # 16. Backend -> Decision Engine integration
    @pytest.mark.asyncio
    async def test_16_backend_decision_integration(self, api_client, auth_headers, field_id):
        decision_payload = {
            "analysis": {
                "crop": {"name": "tomato", "confidence": 0.92},
                "disease": {"name": "early_blight", "confidence": 0.85, "severity": "moderate"},
                "climate_risk": {"drought": 0.1, "heat": 0.1, "flood": 0.0, "waterlogging": 0.0},
            },
            "sensor_data": {"soil": {"moisture_percent": 40.0}},
            "weather_data": {"rain_probability": 15.0, "temperature": 23.0},
        }
        r = await api_client.post(
            "/api/decision",
            params={"field_id": field_id},
            json=decision_payload,
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert "decision_id" in data
        assert data["primary_decision"] == "SPRAY"
        assert data["risk_level"] == "MEDIUM"

    # 17. Decision persistence
    @pytest.mark.asyncio
    async def test_17_decision_persistence(self, api_client, auth_headers, field_id):
        decision_payload = {
            "analysis": {
                "crop": {"name": "wheat", "confidence": 0.95},
                "climate_risk": {"drought": 0.85, "heat": 0.1, "flood": 0.0, "waterlogging": 0.0},
            },
            "sensor_data": {"soil": {"moisture_percent": 15.0}},
            "weather_data": {"rain_probability": 0.0, "temperature": 26.0},
        }
        r = await api_client.post(
            "/api/decision",
            params={"field_id": field_id},
            json=decision_payload,
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        decision_id = data["decision_id"]
        assert decision_id is not None
        assert data["primary_decision"] == "IRRIGATE"

    # 18. Decision TTL
    @pytest.mark.asyncio
    async def test_18_decision_ttl(self, api_client, auth_headers, field_id):
        decision_payload = {
            "analysis": {
                "crop": {"name": "wheat", "confidence": 0.95},
                "disease": {"name": "healthy", "confidence": 0.95},
                "climate_risk": {},
            },
            "weather_data": {},
        }
        r = await api_client.post(
            "/api/decision",
            params={"field_id": field_id},
            json=decision_payload,
            headers=auth_headers,
        )
        assert r.status_code == 200
        # Verify TTL seconds is positive configured value
        assert settings.decision_ttl_seconds > 0

    # 19. Expired decision cannot activate a device
    @pytest.mark.asyncio
    async def test_19_expired_decision_cannot_activate_device(self, api_client, auth_headers, field_id, device_id):
        # Create an expired decision
        from app.database import get_db
        from app.models import Decision
        db = next(get_db())
        try:
            past = datetime.now(timezone.utc) - timedelta(hours=2)
            expired_decision = Decision(
                field_id=field_id,
                primary_decision="SPRAY",
                risk_level="MEDIUM",
                result={"primary_decision": "SPRAY", "risk_level": "MEDIUM", "requires_confirmation": False},
                created_at=past - timedelta(minutes=30),
                expires_at=past,
            )
            db.add(expired_decision)
            db.commit()
            db.refresh(expired_decision)
            expired_id = expired_decision.id
        finally:
            db.close()

        # Try to execute spray command with the expired decision
        cmd_r = await api_client.post(
            f"/api/devices/{device_id}/spray",
            params={"decision_id": expired_id},
            headers=auth_headers,
        )
        assert cmd_r.status_code in (400, 409, 422)
        assert "expired" in cmd_r.json().get("detail", "").lower()

    # 20. Decision Engine failure does not activate a device
    @pytest.mark.asyncio
    async def test_20_decision_failure_does_not_activate_device(self, api_client, auth_headers, field_id, device_id):
        # 1. Direct DecisionService failure behavior
        unreachable_service = DecisionService(base_url="http://nonexistent-decision-host:9999")
        try:
            with pytest.raises(httpx.ConnectError):
                await unreachable_service.decide({"analysis": {}, "weather_data": {}})
        finally:
            await unreachable_service.close()

        # 2. Actuator command boundary: Attempting spray without valid decision must be blocked
        cmd_r = await api_client.post(
            f"/api/devices/{device_id}/spray",
            params={"decision_id": 999999},  # Non-existent decision
            headers=auth_headers,
        )
        assert cmd_r.status_code in (400, 404, 409, 422)
