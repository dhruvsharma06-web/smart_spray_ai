import os
import sys
import time
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.iot.esp32_service import esp32_service, TELEMETRY_TIMEOUT_SECONDS
from app.iot.mock_service import mock_iot_service

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def test_command_queue_and_consumed_only_once(client):
    device_id = "device-test-queue"

    # Queue SPRAY
    res = client.post(f"/api/v1/iot/{device_id}/command", json={"command": "SPRAY", "duration_ms": 4000})
    assert res.status_code == 200
    assert res.json()["status"] == "QUEUED"

    # Poll command first time -> returns SPRAY
    poll1 = client.get(f"/api/v1/iot/{device_id}/command")
    assert poll1.status_code == 200
    data1 = poll1.json()
    assert data1["command"] == "SPRAY"
    assert data1["duration_ms"] == 4000

    # Poll command second time -> consumed only once! -> returns NONE
    poll2 = client.get(f"/api/v1/iot/{device_id}/command")
    assert poll2.status_code == 200
    data2 = poll2.json()
    assert data2["command"] == "NONE"

def test_irrigate_command_queue_and_ack(client):
    device_id = "device-test-irrigate"

    # Queue IRRIGATE
    res = client.post(f"/api/v1/iot/{device_id}/command", json={"command": "IRRIGATE", "duration_ms": 8000})
    assert res.status_code == 200
    assert res.json()["command"] == "IRRIGATE"

    # Consume command
    poll = client.get(f"/api/v1/iot/{device_id}/command")
    assert poll.json()["command"] == "IRRIGATE"

    # ESP32 Sends ACK STARTED
    ack1 = client.post(f"/api/v1/iot/{device_id}/ack", json={"command": "IRRIGATE", "status": "STARTED"})
    assert ack1.status_code == 200
    assert ack1.json()["success"] is True

    # Check status -> IRRIGATING & pump on
    stat1 = client.get(f"/api/v1/devices/{device_id}/status").json()
    assert stat1["current_action"] == "IRRIGATING"
    assert stat1["pump_status"] == "on"

    # ESP32 Sends ACK COMPLETED
    ack2 = client.post(f"/api/v1/iot/{device_id}/ack", json={"command": "IRRIGATE", "status": "COMPLETED"})
    assert ack2.status_code == 200

    # Check status -> IDLE & pump off
    stat2 = client.get(f"/api/v1/devices/{device_id}/status").json()
    assert stat2["current_action"] == "IDLE"
    assert stat2["pump_status"] == "off"

def test_stop_command(client):
    device_id = "device-test-stop"

    res = client.post("/api/v1/spray/stop", json={"device_id": device_id})
    assert res.status_code == 200
    assert res.json()["status"] == "STOPPED"

    # Verify pending command is STOP
    poll = client.get(f"/api/v1/iot/{device_id}/command")
    assert poll.json()["command"] == "STOP"

def test_emergency_stop_command(client):
    device_id = "device-test-estop"

    res = client.post("/api/v1/spray/emergency-stop", json={"device_id": device_id, "reason": "Testing e-stop"})
    assert res.status_code == 200
    assert res.json()["status"] == "EMERGENCY_HALTED"

    poll = client.get(f"/api/v1/iot/{device_id}/command")
    assert poll.json()["command"] == "EMERGENCY_STOP"

    # Attempting to queue SPRAY while in EMERGENCY_HALTED should be rejected
    spray_res = client.post(f"/api/v1/iot/{device_id}/command", json={"command": "SPRAY"})
    assert spray_res.json()["status"] == "REJECTED"

    # Reset emergency stop
    reset_res = client.post("/api/v1/spray/reset-emergency-stop", json={"device_id": device_id})
    assert reset_res.status_code == 200
    assert reset_res.json()["status"] in ("ONLINE", "OFFLINE")

def test_unauthorized_spray_rejected(client):
    device_id = "device-001"

    # Request manual spray with non-existent decision_id -> must be rejected
    res = client.post("/api/v1/spray/manual", json={
        "device_id": device_id,
        "duration_ms": 5000,
        "decision_id": "dec-invalid-999",
    })
    assert res.status_code == 403
    assert res.json()["detail"]["status"] == "REJECTED"

# ==========================================
# HARDWARE STATUS & TELEMETRY TIMEOUT TESTS
# ==========================================

def test_esp32_hardware_status_no_telemetry(client):
    """
    Test A: No telemetry received -> ESP32 = DISCONNECTED (esp32_connected=False),
    status = OFFLINE, sensor values unavailable (soil=None, environment=None).
    """
    dev_id = "device-no-telemetry-test"
    stat = client.get(f"/api/v1/devices/{dev_id}/status").json()

    assert stat["esp32_connected"] is False
    assert stat["status"] == "OFFLINE"
    assert stat["soil"] is None
    assert stat["environment"] is None
    assert stat["pump_status"] == "off"

def test_esp32_hardware_status_recent_telemetry(client):
    """
    Test B: Valid recent telemetry received -> ESP32 = CONNECTED (esp32_connected=True),
    status = ONLINE, real telemetry values displayed.
    """
    dev_id = "device-recent-telemetry-test"
    payload = {
        "device_id": dev_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "soil": {"moisture_percent": 55.4},
        "environment": {
            "temperature_celsius": 26.5,
            "humidity_percent": 60.1,
            "rain_detected": False,
        },
        "pump": False,
    }

    post_res = client.post("/api/sensors/telemetry", json=payload)
    assert post_res.status_code == 201

    stat = client.get(f"/api/v1/devices/{dev_id}/status").json()
    assert stat["esp32_connected"] is True
    assert stat["status"] == "ONLINE"
    assert stat["soil"]["moisture_percent"] == 55.4
    assert stat["environment"]["temperature_celsius"] == 26.5
    assert stat["environment"]["humidity_percent"] == 60.1

def test_esp32_hardware_status_telemetry_timeout(client):
    """
    Test C: Telemetry stops -> after configured TELEMETRY_TIMEOUT_SECONDS (10s),
    ESP32 automatically transitions to DISCONNECTED/OFFLINE and sensor values become None.
    """
    dev_id = "device-timeout-test"
    payload = {
        "device_id": dev_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "soil": {"moisture_percent": 40.0},
        "environment": {
            "temperature_celsius": 25.0,
            "humidity_percent": 50.0,
            "rain_detected": True,
        },
        "pump": False,
    }

    client.post("/api/sensors/telemetry", json=payload)
    stat1 = client.get(f"/api/v1/devices/{dev_id}/status").json()
    assert stat1["esp32_connected"] is True

    # Manually simulate time passing > TELEMETRY_TIMEOUT_SECONDS (10s)
    state = esp32_service._get_or_init_state(dev_id)
    state["last_telemetry_at"] = datetime.now(timezone.utc) - timedelta(seconds=TELEMETRY_TIMEOUT_SECONDS + 2)

    stat2 = client.get(f"/api/v1/devices/{dev_id}/status").json()
    assert stat2["esp32_connected"] is False
    assert stat2["status"] == "OFFLINE"
    assert stat2["soil"] is None
    assert stat2["environment"] is None

def test_mock_iot_cannot_report_real_hardware_connected():
    """
    Test F: Mock IoT cannot make physical ESP32 status appear CONNECTED.
    """
    mock_stat = mock_iot_service.get_status("device-001")
    assert mock_stat["esp32_connected"] is False
    assert mock_stat.get("is_mock") is True

# ==========================================
# REAL PUMP CONTROL, AUTHORIZATION & SAFETY TESTS
# ==========================================

def test_manual_spray_valid_authorization_accepted(client):
    """
    1. Valid manual SPRAY authorization -> accepted.
    7. SPRAY queues through real esp32_service.
    """
    dev_id = "device-001"
    # Ensure default field and device exist and send fresh telemetry
    tel_payload = {
        "device_id": dev_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "soil": {"moisture_percent": 30.0},
        "environment": {"temperature_celsius": 24.0, "humidity_percent": 50.0, "rain_detected": False},
        "pump": False,
    }
    client.post("/api/sensors/telemetry", json=tel_payload)

    # Manual spray without decision_id creates a legitimate MANUAL_OPERATOR decision and passes safety gate
    res = client.post("/api/v1/spray/manual", json={
        "device_id": dev_id,
        "duration_ms": 4000,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["status"] == "QUEUED"
    assert data["is_real_hardware"] is True

    # Check that the real esp32_service has queued the command
    poll = client.get(f"/api/v1/iot/{dev_id}/command")
    assert poll.status_code == 200
    poll_data = poll.json()
    assert poll_data["command"] == "SPRAY"
    assert poll_data["duration_ms"] == 4000

def test_missing_decision_rejected_safely(client):
    """
    2. Missing decision on operational command -> rejected safely.
    """
    # Direct command endpoint requires decision_id for operational actions
    res = client.post("/devices/device-001/command", json={
        "action": "SPRAY",
    })
    assert res.status_code == 403
    assert res.json()["detail"]["authorized"] is False
    assert "Missing decision authorization reference" in res.json()["detail"]["reason"]

def test_expired_decision_rejected_safely(client):
    """
    3. Expired decision -> rejected safely.
    """
    import asyncio
    from sqlalchemy import select
    from app.db.sqlite import AsyncSessionLocal, DecisionModel, DeviceModel, gen_id
    dec_id = gen_id("dec-exp-test-")

    async def _create_exp():
        async with AsyncSessionLocal() as session:
            dev = (await session.execute(select(DeviceModel).where(DeviceModel.id == "device-001"))).scalar_one_or_none()
            field_id = dev.field_id if dev else "field-001"
            dec = DecisionModel(
                id=dec_id,
                field_id=field_id,
                primary_decision="SPRAY",
                risk_level="LOW",
                actions_json=[],
                warnings_json=[],
                requires_confirmation=False,
                raw_decision_json={},
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            )
            session.add(dec)
            await session.commit()
    asyncio.run(_create_exp())

    res = client.post("/api/v1/spray/manual", json={
        "device_id": "device-001",
        "decision_id": dec_id,
    })
    assert res.status_code == 403
    assert "expired" in res.json()["detail"]["message"].lower()

def test_offline_esp32_manual_spray_rejected(client):
    """
    4. Offline ESP32 -> rejected.
    """
    dev_id = "device-001"
    # Ensure offline by setting last_telemetry_at to None
    state = esp32_service._get_or_init_state(dev_id)
    state["last_telemetry_at"] = None

    res = client.post("/api/v1/spray/manual", json={
        "device_id": dev_id,
        "duration_ms": 5000,
    })
    assert res.status_code == 403
    assert "offline or telemetry is stale" in res.json()["detail"]["message"]

def test_stale_telemetry_manual_spray_rejected(client):
    """
    5. Stale telemetry -> rejected.
    """
    dev_id = "device-001"
    # Set telemetry older than TELEMETRY_TIMEOUT_SECONDS
    state = esp32_service._get_or_init_state(dev_id)
    state["last_telemetry_at"] = datetime.now(timezone.utc) - timedelta(seconds=TELEMETRY_TIMEOUT_SECONDS + 5)

    res = client.post("/api/v1/spray/manual", json={
        "device_id": dev_id,
        "duration_ms": 5000,
    })
    assert res.status_code == 403
    assert "offline or telemetry is stale" in res.json()["detail"]["message"]

def test_emergency_stop_always_works_and_blocks_pumps(client):
    """
    6. Emergency STOP -> always works.
    15. Emergency stop turns both OFF.
    """
    dev_id = "device-001"
    # Emergency stop
    em_res = client.post("/api/v1/spray/emergency-stop", json={"device_id": dev_id, "reason": "Test safety stop"})
    assert em_res.status_code == 200
    assert em_res.json()["status"] == "EMERGENCY_HALTED"

    # Consume queued EMERGENCY_STOP command
    poll1 = client.get(f"/api/v1/iot/{dev_id}/command")
    assert poll1.json()["command"] == "EMERGENCY_STOP"

    # Even with fresh telemetry, manual spray must be blocked while in EMERGENCY_HALTED
    client.post("/api/sensors/telemetry", json={
        "device_id": dev_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "soil": {"moisture_percent": 30.0},
        "environment": {"temperature_celsius": 24.0, "humidity_percent": 50.0, "rain_detected": False},
        "pump": False,
    })
    res = client.post("/api/v1/spray/manual", json={"device_id": dev_id, "duration_ms": 5000})
    assert res.status_code == 403
    assert "EMERGENCY_HALTED" in res.json()["detail"]["message"]

    # Reset emergency stop
    reset_res = client.post("/api/v1/spray/reset-emergency-stop", json={"device_id": dev_id})
    assert reset_res.status_code == 200
    assert reset_res.json()["status"] == "ONLINE"

    # Consume queued RESET command
    poll2 = client.get(f"/api/v1/iot/{dev_id}/command")
    assert poll2.json()["command"] == "RESET"

def test_irrigate_queues_through_real_esp32_service(client):
    """
    8. IRRIGATE queues through real esp32_service.
    """
    dev_id = "device-001"
    client.post("/api/sensors/telemetry", json={
        "device_id": dev_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "soil": {"moisture_percent": 30.0},
        "environment": {"temperature_celsius": 24.0, "humidity_percent": 50.0, "rain_detected": False},
        "pump": False,
    })

    res = client.post("/api/v1/spray/irrigate", json={
        "device_id": dev_id,
        "duration_ms": 6000,
    })
    assert res.status_code == 200
    assert res.json()["status"] == "QUEUED"
    assert res.json()["is_real_hardware"] is True

    poll = client.get(f"/api/v1/iot/{dev_id}/command")
    assert poll.json()["command"] == "IRRIGATE"
    assert poll.json()["duration_ms"] == 6000

def test_esp32_started_and_completed_ack_state(client):
    """
    9. ESP32 STARTED ACK updates state.
    10. ESP32 COMPLETED ACK updates state.
    """
    dev_id = "device-001"
    # Started
    ack_start = client.post(f"/api/v1/iot/{dev_id}/ack", json={"command": "SPRAY", "status": "STARTED"})
    assert ack_start.status_code == 200
    stat1 = client.get(f"/api/v1/devices/{dev_id}/status").json()
    assert stat1["current_action"] == "SPRAYING"
    assert stat1["pump_status"] == "on"

    # Completed
    ack_comp = client.post(f"/api/v1/iot/{dev_id}/ack", json={"command": "SPRAY", "status": "COMPLETED"})
    assert ack_comp.status_code == 200
    stat2 = client.get(f"/api/v1/devices/{dev_id}/status").json()
    assert stat2["current_action"] == "IDLE"
    assert stat2["pump_status"] == "off"

def test_simultaneous_pump_protection(client):
    """
    13. Both pumps can never be ON simultaneously.
    """
    dev_id = "device-001"
    client.post("/api/sensors/telemetry", json={
        "device_id": dev_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "soil": {"moisture_percent": 30.0},
        "environment": {"temperature_celsius": 24.0, "humidity_percent": 50.0, "rain_detected": False},
        "pump": True,
    })
    state = esp32_service._get_or_init_state(dev_id)
    state["current_action"] = "IRRIGATING"

    # Attempting to SPRAY while IRRIGATING must be rejected
    res = client.post("/api/v1/spray/manual", json={"device_id": dev_id, "duration_ms": 5000})
    assert res.status_code == 403
    assert "currently IRRIGATING" in res.json()["detail"]["message"]

    # Clean up state
    state["current_action"] = "IDLE"

def test_duration_safety_limit_enforced(client):
    """
    16. Duration cannot exceed safety limit (30 seconds).
    """
    dev_id = "device-001"
    client.post("/api/sensors/telemetry", json={
        "device_id": dev_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "soil": {"moisture_percent": 30.0},
        "environment": {"temperature_celsius": 24.0, "humidity_percent": 50.0, "rain_detected": False},
        "pump": False,
    })

    # Duration > 30000ms must be rejected
    res = client.post("/api/v1/spray/manual", json={
        "device_id": dev_id,
        "duration_ms": 35000,
    })
    assert res.status_code == 403
    assert "exceeds maximum safety limit" in res.json()["detail"]["message"]

def test_valid_manual_irrigate_accepted_and_creates_decision(client):
    """
    1. Valid manual IRRIGATE request -> accepted.
    2. Manual IRRIGATE creates decision with action IRRIGATE.
    3. IRRIGATE queues through esp32_service.
    """
    import asyncio
    from sqlalchemy import select
    from app.db.sqlite import AsyncSessionLocal, DecisionModel

    dev_id = "device-001"
    client.post("/api/sensors/telemetry", json={
        "device_id": dev_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "soil": {"moisture_percent": 25.0},
        "environment": {"temperature_celsius": 28.0, "humidity_percent": 45.0, "rain_detected": False},
        "pump": False,
    })

    # Clear pending commands
    client.get(f"/api/v1/iot/{dev_id}/command")

    res = client.post("/api/v1/spray/irrigate", json={
        "device_id": dev_id,
        "duration_ms": 7000,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["status"] == "QUEUED"
    assert data["is_real_hardware"] is True

    # Check ESP32 command queue
    poll = client.get(f"/api/v1/iot/{dev_id}/command")
    assert poll.status_code == 200
    poll_data = poll.json()
    assert poll_data["command"] == "IRRIGATE"
    assert poll_data["duration_ms"] == 7000

    # Verify that the created decision in DecisionModel has primary_decision == "IRRIGATE"
    async def _verify_decision():
        async with AsyncSessionLocal() as session:
            stmt = select(DecisionModel).order_by(DecisionModel.timestamp.desc()).limit(1)
            dec = (await session.execute(stmt)).scalar_one_or_none()
            assert dec is not None
            assert dec.primary_decision == "IRRIGATE"
            assert dec.actions_json[0]["action"] == "IRRIGATE"
    asyncio.run(_verify_decision())

def test_irrigate_cannot_run_while_spraying(client):
    """
    4. IRRIGATE cannot run while SPRAYING.
    """
    dev_id = "device-001"
    client.post("/api/sensors/telemetry", json={
        "device_id": dev_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "soil": {"moisture_percent": 30.0},
        "environment": {"temperature_celsius": 24.0, "humidity_percent": 50.0, "rain_detected": False},
        "pump": True,
    })
    state = esp32_service._get_or_init_state(dev_id)
    state["current_action"] = "SPRAYING"

    res = client.post("/api/v1/spray/irrigate", json={"device_id": dev_id, "duration_ms": 5000})
    assert res.status_code == 403
    assert "currently SPRAYING" in res.json()["detail"]["message"]

    state["current_action"] = "IDLE"

def test_stale_telemetry_rejects_irrigate(client):
    """
    6. Stale telemetry rejects IRRIGATE.
    """
    dev_id = "device-001"
    state = esp32_service._get_or_init_state(dev_id)
    state["last_telemetry_at"] = datetime.now(timezone.utc) - timedelta(seconds=TELEMETRY_TIMEOUT_SECONDS + 5)

    res = client.post("/api/v1/spray/irrigate", json={
        "device_id": dev_id,
        "duration_ms": 5000,
    })
    assert res.status_code == 403
    assert "offline or telemetry is stale" in res.json()["detail"]["message"]

def test_emergency_stop_rejects_irrigate(client):
    """
    7. Emergency stop rejects IRRIGATE.
    """
    dev_id = "device-001"
    em_res = client.post("/api/v1/spray/emergency-stop", json={"device_id": dev_id, "reason": "Test safety stop"})
    assert em_res.status_code == 200
    assert em_res.json()["status"] == "EMERGENCY_HALTED"

    # Consume queued command
    client.get(f"/api/v1/iot/{dev_id}/command")

    # Send fresh telemetry
    client.post("/api/sensors/telemetry", json={
        "device_id": dev_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "soil": {"moisture_percent": 30.0},
        "environment": {"temperature_celsius": 24.0, "humidity_percent": 50.0, "rain_detected": False},
        "pump": False,
    })

    res = client.post("/api/v1/spray/irrigate", json={"device_id": dev_id, "duration_ms": 5000})
    assert res.status_code == 403
    assert "EMERGENCY_HALTED" in res.json()["detail"]["message"]

    # Reset
    reset_res = client.post("/api/v1/spray/reset-emergency-stop", json={"device_id": dev_id})
    assert reset_res.status_code == 200
    client.get(f"/api/v1/iot/{dev_id}/command")

def test_duration_exceeding_30s_rejects_irrigate(client):
    """
    8. Duration > 30 sec rejects IRRIGATE.
    """
    dev_id = "device-001"
    client.post("/api/sensors/telemetry", json={
        "device_id": dev_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "soil": {"moisture_percent": 30.0},
        "environment": {"temperature_celsius": 24.0, "humidity_percent": 50.0, "rain_detected": False},
        "pump": False,
    })

    res = client.post("/api/v1/spray/irrigate", json={
        "device_id": dev_id,
        "duration_ms": 35000,
    })
    assert res.status_code == 403
    assert "exceeds maximum safety limit" in res.json()["detail"]["message"]

def test_static_firmware_relay_mapping_verification():
    """
    11. SPRAY activates GPIO25 only (Relay CH2).
    12. IRRIGATE activates GPIO26 only (Relay CH1).
    14. STOP turns both OFF.
    17. Unknown command leaves both pumps OFF.
    """
    firmware_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../firmware/smart_spray_esp32/smart_spray_esp32.ino"))
    assert os.path.exists(firmware_path)
    with open(firmware_path, "r", encoding="utf-8") as f:
        src = f.read()

    # Pin mappings: SPRAY -> GPIO25 (CH2), IRRIGATE -> GPIO26 (CH1)
    assert "#define RELAY_SPRAY      25" in src
    assert "#define RELAY_IRRIGATION 26" in src
    assert "#define RELAY_ON         LOW" in src
    assert "#define RELAY_OFF        HIGH" in src

    # SPRAY command turns GPIO25 ON and GPIO26 OFF
    assert "digitalWrite(RELAY_IRRIGATION, RELAY_OFF);" in src
    assert "digitalWrite(RELAY_SPRAY, RELAY_ON);" in src

    # IRRIGATE command turns GPIO26 ON and GPIO25 OFF
    assert "digitalWrite(RELAY_SPRAY, RELAY_OFF);" in src
    assert "digitalWrite(RELAY_IRRIGATION, RELAY_ON);" in src

    # STOP / turnOffAllPumps turns both OFF
    assert "digitalWrite(RELAY_SPRAY, RELAY_OFF);" in src
    assert "digitalWrite(RELAY_IRRIGATION, RELAY_OFF);" in src

    # Safety max duration
    assert "MAX_SAFETY_DURATION   = 30000UL" in src
