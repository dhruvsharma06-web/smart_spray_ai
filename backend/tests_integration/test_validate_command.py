import pytest
from app.iot.commands import validate_command
from app.models import Device
from datetime import datetime, timezone
from fastapi import HTTPException


class TestValidateCommand:
    """Unit tests for the validate_command function."""

    def make_device(self, status="ONLINE", tank_level=80):
        return Device(
            id=1,
            field_id=1,
            device_uid="test-device",
            name="Test Device",
            device_type="ESP32",
            status=status,
            last_seen_at=datetime.now(timezone.utc),
            tank_level=tank_level,
            pump_active=False
        )

    def test_validate_spray_requires_decision(self):
        device = self.make_device()
        with pytest.raises(HTTPException) as exc:
            validate_command(device, "spray", decision=None)
        assert exc.value.status_code == 409
        assert "requires an approved decision" in exc.value.detail

    def test_validate_spray_rejects_non_spray_decision(self):
        device = self.make_device()
        decision = {"primary_decision": "IRRIGATE", "risk_level": "MEDIUM", "requires_confirmation": False}
        with pytest.raises(HTTPException) as exc:
            validate_command(device, "spray", decision=decision)
        assert exc.value.status_code == 409
        assert "not authorized" in exc.value.detail.lower()

    def test_validate_spray_rejects_delay_decision(self):
        device = self.make_device()
        decision = {"primary_decision": "DELAY_SPRAY", "risk_level": "HIGH", "requires_confirmation": False}
        with pytest.raises(HTTPException) as exc:
            validate_command(device, "spray", decision=decision)
        assert exc.value.status_code == 409
        assert "not authorized" in exc.value.detail.lower()

    def test_validate_spray_rejects_critical_risk(self):
        device = self.make_device()
        decision = {"primary_decision": "SPRAY", "risk_level": "CRITICAL", "requires_confirmation": False}
        with pytest.raises(HTTPException) as exc:
            validate_command(device, "spray", decision=decision)
        assert exc.value.status_code == 409
        assert "critical" in exc.value.detail.lower()

    def test_validate_spray_rejects_requires_confirmation(self):
        device = self.make_device()
        decision = {"primary_decision": "SPRAY", "risk_level": "MEDIUM", "requires_confirmation": True}
        with pytest.raises(HTTPException) as exc:
            validate_command(device, "spray", decision=decision)
        assert exc.value.status_code == 409
        assert "confirmation" in exc.value.detail.lower()

    def test_validate_spray_accepts_valid_decision(self):
        device = self.make_device()
        decision = {"primary_decision": "SPRAY", "risk_level": "MEDIUM", "requires_confirmation": False}
        # Should not raise
        validate_command(device, "spray", decision=decision)

    def test_validate_irrigate_requires_decision(self):
        device = self.make_device()
        with pytest.raises(HTTPException) as exc:
            validate_command(device, "irrigate", decision=None)
        assert exc.value.status_code == 409
        assert "requires an approved decision" in exc.value.detail

    def test_validate_irrigate_rejects_non_irrigate_decision(self):
        device = self.make_device()
        decision = {"primary_decision": "SPRAY", "risk_level": "MEDIUM", "requires_confirmation": False}
        with pytest.raises(HTTPException) as exc:
            validate_command(device, "irrigate", decision=decision)
        assert exc.value.status_code == 409
        assert "not authorized" in exc.value.detail.lower()

    def test_validate_irrigate_rejects_requires_confirmation(self):
        device = self.make_device()
        decision = {"primary_decision": "IRRIGATE", "risk_level": "MEDIUM", "requires_confirmation": True}
        with pytest.raises(HTTPException) as exc:
            validate_command(device, "irrigate", decision=decision)
        assert exc.value.status_code == 409
        assert "confirmation" in exc.value.detail.lower()

    def test_validate_irrigate_accepts_valid_decision(self):
        device = self.make_device()
        decision = {"primary_decision": "IRRIGATE", "risk_level": "HIGH", "requires_confirmation": False}
        validate_command(device, "irrigate", decision=decision)

    def test_validate_stop_requires_no_decision(self):
        device = self.make_device()
        # Should not raise
        validate_command(device, "stop", decision=None)

    def test_validate_rejects_offline_device_for_spray(self):
        device = self.make_device(status="OFFLINE")
        decision = {"primary_decision": "SPRAY", "risk_level": "MEDIUM", "requires_confirmation": False}
        with pytest.raises(HTTPException) as exc:
            validate_command(device, "spray", decision=decision)
        assert exc.value.status_code == 409
        assert "offline" in exc.value.detail.lower()

    def test_validate_rejects_offline_device_for_irrigate(self):
        device = self.make_device(status="OFFLINE")
        decision = {"primary_decision": "IRRIGATE", "risk_level": "MEDIUM", "requires_confirmation": False}
        with pytest.raises(HTTPException) as exc:
            validate_command(device, "irrigate", decision=decision)
        assert exc.value.status_code == 409
        assert "offline" in exc.value.detail.lower()

    def test_validate_allows_stop_on_offline_device(self):
        device = self.make_device(status="OFFLINE")
        # Should not raise
        validate_command(device, "stop", decision=None)

    def test_validate_rejects_low_tank_for_spray(self):
        device = self.make_device(tank_level=3)
        decision = {"primary_decision": "SPRAY", "risk_level": "MEDIUM", "requires_confirmation": False}
        with pytest.raises(HTTPException) as exc:
            validate_command(device, "spray", decision=decision)
        assert exc.value.status_code == 409
        assert "tank" in exc.value.detail.lower()

    def test_validate_rejects_low_tank_for_irrigate(self):
        device = self.make_device(tank_level=3)
        decision = {"primary_decision": "IRRIGATE", "risk_level": "MEDIUM", "requires_confirmation": False}
        with pytest.raises(HTTPException) as exc:
            validate_command(device, "irrigate", decision=decision)
        assert exc.value.status_code == 409
        assert "tank" in exc.value.detail.lower()

    def test_validate_allows_low_tank_for_stop(self):
        device = self.make_device(tank_level=0)
        validate_command(device, "stop", decision=None)

    def test_validate_rejects_unknown_action(self):
        device = self.make_device()
        with pytest.raises(HTTPException) as exc:
            validate_command(device, "explode", decision=None)
        assert exc.value.status_code == 400
        assert "unsupported" in exc.value.detail.lower()

    def test_validate_spray_with_none_decision(self):
        device = self.make_device()
        with pytest.raises(HTTPException) as exc:
            validate_command(device, "spray", decision=None)
        assert exc.value.status_code == 409

    def test_validate_irrigate_with_none_decision(self):
        device = self.make_device()
        with pytest.raises(HTTPException) as exc:
            validate_command(device, "irrigate", decision=None)
        assert exc.value.status_code == 409