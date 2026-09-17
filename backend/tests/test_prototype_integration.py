import io
import json
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.db.sqlite import (
    init_sqlite_db,
    AsyncSessionLocal,
    sqlite_engine,
    SQLiteBase,
    gen_id,
    FieldModel,
    DeviceModel,
    DecisionModel,
    ActionHistoryModel,
    utc_now,
)
from app.services.actuator_authorization import ActuatorAuthorizationService

@pytest.fixture(scope="session", autouse=True)
def init_db():
    import asyncio
    async def _setup():
        async with sqlite_engine.begin() as conn:
            await conn.run_sync(SQLiteBase.metadata.drop_all)
            await conn.run_sync(SQLiteBase.metadata.create_all)
    asyncio.run(_setup())

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

# ======================================================
# 1. Field, Device, Telemetry, and Zone Tests
# ======================================================

def test_01_create_field(client):
    res = client.post("/fields", json={
        "id": "field-test-01",
        "name": "Test Tomato Field Alpha",
        "crop_type": "Tomato",
        "latitude": 19.0760,
        "longitude": 72.8777,
    })
    assert res.status_code == 201
    data = res.json()
    assert data["id"] == "field-test-01"
    assert data["name"] == "Test Tomato Field Alpha"
    assert data["crop_type"] == "Tomato"

def test_02_create_device(client):
    res = client.post("/devices", json={
        "id": "device-test-01",
        "field_id": "field-test-01",
        "name": "SmartSpray Test Rig 1",
    })
    assert res.status_code == 201
    data = res.json()
    assert data["id"] == "device-test-01"
    assert data["field_id"] == "field-test-01"

def test_03_post_telemetry(client):
    res = client.post("/telemetry", json={
        "field_id": "field-test-01",
        "device_id": "device-test-01",
        "soil_moisture": 24.5,
        "soil_temperature": 28.0,
        "air_temperature": 32.0,
        "humidity": 65.0,
        "rainfall": 0.0,
    })
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "INGESTED"
    assert data["field_id"] == "field-test-01"
    assert data["device_id"] == "device-test-01"

def test_04_get_device_status(client):
    res = client.get("/devices/device-test-01/status")
    assert res.status_code == 200
    data = res.json()
    assert data["device_id"] == "device-test-01"
    assert "status" in data
    assert "battery" in data
    assert "tank_level" in data

def test_05_get_field_latest(client):
    res = client.get("/fields/field-test-01/latest")
    assert res.status_code == 200
    data = res.json()
    assert data["field"]["id"] == "field-test-01"
    assert len(data["devices"]) >= 1
    assert data["latest_telemetry"] is not None
    assert data["latest_telemetry"]["soil_moisture"] == 24.5

def test_06_get_field_history(client):
    res = client.get("/fields/field-test-01/history")
    assert res.status_code == 200
    data = res.json()
    assert data["field_id"] == "field-test-01"
    assert "analyses" in data
    assert "decisions" in data
    assert "actions" in data

def test_07_get_field_zones(client):
    res = client.get("/fields/field-test-01/zones")
    assert res.status_code == 200
    zones = res.json()
    assert isinstance(zones, list)
    assert len(zones) >= 1
    assert "boundary" in zones[0]

# ======================================================
# 2. Central POST /analyze and Deterministic Demo Scenarios
# ======================================================

def test_08_analyze_happy_path_demo_mode(client):
    fake_img = io.BytesIO(b"dummy image bytes for testing")
    res = client.post(
        "/analyze",
        files={"image": ("tomato_leaf.jpg", fake_img, "image/jpeg")},
        data={"field_id": "field-test-01", "crop_stage": "vegetative"},
        headers={"X-Demo-Scenario": "TOMATO_EARLY_BLIGHT"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "analysis_id" in data
    assert "decision_id" in data
    assert data["analysis"]["crop"]["name"] == "Tomato"
    assert data["decision"]["primary_decision"] == "SPRAY"
    assert data["actuation"]["authorized"] is True
    assert data["actuation"]["executed"] is True
    assert data["actuation"]["action"] == "SPRAY"
    assert data["actuation"]["status"] == "SIMULATED"
    assert data["execution_metadata"]["actuation_type"] == "SIMULATED_MOCK_IOT"

def test_09_analyze_ai_failure_handling(client):
    fake_img = io.BytesIO(b"dummy image bytes")
    # Patch AIService in non-demo mode to simulate connection failure
    with patch("app.config.settings.demo_mode", False):
        with patch("app.ai.client.AIService.analyze", side_effect=RuntimeError("Connection refused to :8001")):
            res = client.post(
                "/analyze",
                files={"image": ("leaf.jpg", fake_img, "image/jpeg")},
                data={"field_id": "field-test-01"},
            )
            assert res.status_code == 503
            assert "Person 1 AI Service" in res.json()["detail"]

def test_10_analyze_decision_failure_handling(client):
    fake_img = io.BytesIO(b"dummy image bytes")
    # Patch DecisionEngine to raise error
    with patch("decision.engine.decision_engine.evaluate", side_effect=RuntimeError("Decision engine crashed")):
        with patch("app.decision.client.DecisionService.decide", side_effect=RuntimeError("HTTP 8002 down")):
            res = client.post(
                "/analyze",
                files={"image": ("leaf.jpg", fake_img, "image/jpeg")},
                data={"field_id": "field-test-01"},
                headers={"X-Demo-Scenario": "TOMATO_EARLY_BLIGHT"},
            )
            assert res.status_code == 503
            assert "Decision Engine unavailable" in res.json()["detail"]

def test_11_demo_scenario_tomato_early_blight_authorizes_spray(client):
    fake_img = io.BytesIO(b"tomato leaf bytes")
    res = client.post(
        "/analyze",
        files={"image": ("tomato.jpg", fake_img, "image/jpeg")},
        data={"field_id": "field-test-01"},
        headers={"X-Demo-Scenario": "TOMATO_EARLY_BLIGHT"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["decision"]["primary_decision"] == "SPRAY"
    assert data["actuation"]["authorized"] is True
    assert data["actuation"]["status"] == "SIMULATED"

def test_12_demo_scenario_disease_heavy_rain_blocks_spray(client):
    fake_img = io.BytesIO(b"rain leaf bytes")
    res = client.post(
        "/analyze",
        files={"image": ("rain_tomato.jpg", fake_img, "image/jpeg")},
        data={"field_id": "field-test-01"},
        headers={"X-Demo-Scenario": "DISEASE_HEAVY_RAIN"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["decision"]["primary_decision"] == "DELAY_SPRAY"
    assert data["decision"]["risk_level"] == "HIGH"
    assert data["actuation"]["authorized"] is False
    assert data["actuation"]["executed"] is False
    assert data["actuation"]["status"] == "DELAYED"

def test_13_demo_scenario_healthy_monitors_no_spray(client):
    fake_img = io.BytesIO(b"healthy leaf bytes")
    res = client.post(
        "/analyze",
        files={"image": ("healthy.jpg", fake_img, "image/jpeg")},
        data={"field_id": "field-test-01"},
        headers={"X-Demo-Scenario": "HEALTHY"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["decision"]["primary_decision"] == "MONITOR"
    assert data["actuation"]["authorized"] is False
    assert data["actuation"]["status"] == "INHIBITED"

def test_14_demo_scenario_low_moisture_heat_authorizes_irrigation(client):
    fake_img = io.BytesIO(b"dry soil leaf bytes")
    res = client.post(
        "/analyze",
        files={"image": ("dry_soil.jpg", fake_img, "image/jpeg")},
        data={"field_id": "field-test-01"},
        headers={"X-Demo-Scenario": "LOW_MOISTURE_HEAT"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["decision"]["primary_decision"] == "IRRIGATE"
    assert data["actuation"]["authorized"] is True
    assert data["actuation"]["action"] == "IRRIGATE"
    assert data["actuation"]["status"] == "SIMULATED"

def test_15_demo_scenario_low_confidence_blocks_spray_and_warns(client):
    fake_img = io.BytesIO(b"blurry leaf bytes")
    res = client.post(
        "/analyze",
        files={"image": ("blurry.jpg", fake_img, "image/jpeg")},
        data={"field_id": "field-test-01"},
        headers={"X-Demo-Scenario": "LOW_CONFIDENCE"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["decision"]["primary_decision"] == "WARN"
    assert data["decision"]["requires_confirmation"] is True
    assert data["actuation"]["authorized"] is False
    assert data["actuation"]["status"] == "WARNING"

# ======================================================
# 3. Actuator Safety Gate & Command Tests
# ======================================================

def test_16_independent_stop_bypasses_decision_check(client):
    res = client.post("/devices/device-test-01/command", json={
        "action": "STOP"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["action"] == "STOP"
    assert data["status"] == "STOPPED"

def test_17_independent_emergency_stop_bypasses_decision_check(client):
    res = client.post("/devices/device-test-01/command", json={
        "action": "EMERGENCY_STOP",
        "reason": "Operator sighted animal in field",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["action"] == "EMERGENCY_STOP"
    assert data["status"] == "EMERGENCY_HALTED"

    # Verify device status reflects error / halted state
    stat_res = client.get("/devices/device-test-01/status")
    assert stat_res.status_code == 200
    assert stat_res.json()["current_action"] == "EMERGENCY_HALTED"

    # Reset emergency stop to clear test state
    reset_res = client.post("/devices/device-test-01/command", json={"action": "RESET_EMERGENCY_STOP"})
    assert reset_res.status_code == 200

def test_18_invalid_decision_id_rejected(client):
    res = client.post("/devices/device-test-01/command", json={
        "action": "SPRAY",
        "decision_id": "dec-nonexistent-9999",
    })
    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["authorized"] is False
    assert "does not exist" in detail["reason"]

def test_19_expired_decision_rejected(client):
    import asyncio
    dec_id = gen_id("dec-exp-")
    async def create_expired_dec():
        async with AsyncSessionLocal() as session:
            dec = DecisionModel(
                id=dec_id,
                field_id="field-test-01",
                primary_decision="SPRAY",
                risk_level="MEDIUM",
                actions_json=[{"type": "SPRAY", "priority": "HIGH"}],
                warnings_json=[],
                requires_confirmation=False,
                raw_decision_json={"primary_decision": "SPRAY"},
                expires_at=utc_now() - timedelta(minutes=10),
            )
            session.add(dec)
            await session.commit()
    asyncio.run(create_expired_dec())

    res = client.post("/devices/device-test-01/command", json={
        "action": "SPRAY",
        "decision_id": dec_id,
    })
    assert res.status_code == 403
    assert "expired" in res.json()["detail"]["reason"]

def test_20_incompatible_actuator_command_rejected(client):
    import asyncio
    dec_id = gen_id("dec-val-")
    async def create_spray_dec():
        async with AsyncSessionLocal() as session:
            dec = DecisionModel(
                id=dec_id,
                field_id="field-test-01",
                primary_decision="SPRAY",
                risk_level="MEDIUM",
                actions_json=[{"type": "SPRAY", "priority": "HIGH"}],
                warnings_json=[],
                requires_confirmation=False,
                raw_decision_json={"primary_decision": "SPRAY"},
                expires_at=utc_now() + timedelta(minutes=30),
            )
            session.add(dec)
            await session.commit()
    asyncio.run(create_spray_dec())

    # Requesting IRRIGATE on a SPRAY decision must be rejected by the single safety gate!
    res = client.post("/devices/device-test-01/command", json={
        "action": "IRRIGATE",
        "decision_id": dec_id,
    })
    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["authorized"] is False
    assert "incompatible" in detail["reason"].lower()

# ======================================================
# 4. Flutter Compatibility Layer (/api/v1) Tests
# ======================================================

def test_21_flutter_ai_detect_endpoint(client):
    fake_img = io.BytesIO(b"flutter leaf bytes")
    res = client.post(
        "/api/v1/ai/detect",
        files={"file": ("flutter_leaf.jpg", fake_img, "image/jpeg")},
        data={"crop_type": "Tomato", "field_id": "field-test-01"},
        headers={"X-Demo-Scenario": "TOMATO_EARLY_BLIGHT"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "data" in data
    assert "disease" in data["data"]
    assert "crop" in data["data"]
    assert "decision" in data
    assert data["decision"]["recommendation"] == "SPRAY"
    assert data["decision"]["auto_permitted"] is True

def test_22_flutter_device_status(client):
    res = client.get("/api/v1/devices/device-test-01/status")
    assert res.status_code == 200
    data = res.json()
    assert data["device_id"] == "device-test-01"
    assert "status" in data
    assert "tank_level" in data

def test_23_flutter_spray_controls_and_history(client):
    # Stop
    stop_res = client.post("/api/v1/spray/stop", json={"device_id": "device-test-01"})
    assert stop_res.status_code == 200
    assert stop_res.json()["status"] == "STOPPED"

    # Emergency stop
    em_res = client.post("/api/v1/spray/emergency-stop", json={
        "device_id": "device-test-01",
        "reason": "Test emergency halt from Flutter",
    })
    assert em_res.status_code == 200
    assert em_res.json()["status"] == "EMERGENCY_HALTED"

    # Reset
    reset_res = client.post("/api/v1/spray/reset-emergency-stop", json={"device_id": "device-test-01"})
    assert reset_res.status_code == 200
    assert reset_res.json()["status"] == "ONLINE"

    # History
    hist_res = client.get("/api/v1/spray/history?device_id=device-test-01")
    assert hist_res.status_code == 200
    history = hist_res.json()
    assert isinstance(history, list)
    assert len(history) >= 1
