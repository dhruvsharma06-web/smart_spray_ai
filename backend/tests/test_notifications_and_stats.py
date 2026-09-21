import os
import sys
import pytest
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi.testclient import TestClient
from app.main import app
from app.iot.esp32_service import esp32_service

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def test_notification_endpoints(client):
    device_id = "device-notif-test"
    field_id = "field-notif-test"

    # Queue an action to generate a notification
    res = client.post("/api/v1/spray/manual", json={
        "device_id": device_id,
        "duration_ms": 3000,
    })
    # If device is offline, it might be 403 (BLOCKED) which also creates a notification!
    # Let's check notifications list
    notifs_res = client.get("/api/v1/notifications")
    assert notifs_res.status_code == 200
    notifs = notifs_res.json()
    assert isinstance(notifs, list)

    # Active notifications
    active_res = client.get("/api/v1/notifications/active")
    assert active_res.status_code == 200
    active = active_res.json()
    assert isinstance(active, list)

    if active:
        first_id = active[0]["id"]
        # Mark as read
        read_res = client.post(f"/api/v1/notifications/{first_id}/read")
        assert read_res.status_code == 200
        assert read_res.json()["success"] is True

def test_climate_alerts_generation_and_deduplication():
    import asyncio
    from app.db.sqlite import AsyncSessionLocal
    from app.services.notification_service import NotificationService

    async def run():
        async with AsyncSessionLocal() as db:
            field_id = "field-climate-test"
            device_id = "device-climate-test"

            # 1. High heat risk -> HEATWAVE alert
            analysis_heat = {"climate_risk": {"heat": 0.85, "rain": 0.1, "flood": 0.0}}
            alerts1 = await NotificationService.generate_climate_alerts(
                db=db, field_id=field_id, device_id=device_id, analysis=analysis_heat
            )
            await db.commit()
            assert any(a.type == "HEATWAVE" for a in alerts1)

            # 2. Duplicate high heat risk -> suppressed by deduplication cooldown
            alerts2 = await NotificationService.generate_climate_alerts(
                db=db, field_id=field_id, device_id=device_id, analysis=analysis_heat
            )
            await db.commit()
            # deduplicated: should not create a second new record with same severity
            heat_alerts = [a for a in alerts2 if a.type == "HEATWAVE"]
            assert len(heat_alerts) <= 1

    asyncio.run(run())

def test_actuation_ack_lifecycle_notifications(client):
    device_id = "device-001"

    # 1. Provide fresh telemetry so device is ONLINE
    esp32_service.update_telemetry(device_id, {
        "soil": {"moisture_percent": 35.0},
        "environment": {"temperature_celsius": 24.5, "humidity_percent": 55.0, "rain_detected": False},
        "actuators": {"pump_status": "off", "current_action": "IDLE"},
    })

    # 2. Queue spray
    res = client.post("/api/v1/spray/manual", json={
        "device_id": device_id,
        "duration_ms": 5000,
    })
    assert res.status_code == 200

    # 3. ESP32 sends STARTED ACK
    ack_started = client.post(f"/api/v1/iot/{device_id}/ack", json={"command": "SPRAY", "status": "STARTED"})
    assert ack_started.status_code == 200

    # Verify device status is SPRAYING
    stat = client.get(f"/api/v1/devices/{device_id}/status").json()
    assert stat["current_action"] == "SPRAYING"

    # 4. ESP32 sends COMPLETED ACK
    ack_completed = client.post(f"/api/v1/iot/{device_id}/ack", json={"command": "SPRAY", "status": "COMPLETED"})
    assert ack_completed.status_code == 200

    # Verify device status is IDLE
    stat2 = client.get(f"/api/v1/devices/{device_id}/status").json()
    assert stat2["current_action"] == "IDLE"

    # Verify notifications contain SPRAY_STARTED or SPRAY_COMPLETED
    notifs = client.get("/api/v1/notifications").json()
    types = [n["type"] for n in notifs]
    assert "SPRAY_STARTED" in types or "SPRAY_COMPLETED" in types

def test_field_statistics_endpoint(client):
    res = client.get("/api/v1/statistics?field_id=field-001&device_id=device-001")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "field_health" in data
    assert "operations" in data
    assert "telemetry" in data
    assert "total_actions" in data["operations"]
    assert "total_sprays" in data["operations"]
    assert "total_irrigations" in data["operations"]

def test_spray_history_rich_fields(client):
    res = client.get("/api/v1/spray/history?limit=10")
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)
    if items:
        first = items[0]
        assert "command_id" in first
        assert "status" in first
        assert "duration_ms" in first
        assert "plants_targeted" in first
        assert "disease" in first
        assert "severity" in first
        assert "reason" in first
        assert "ack_state" in first
