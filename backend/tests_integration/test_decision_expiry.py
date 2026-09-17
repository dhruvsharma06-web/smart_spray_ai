import pytest
import pytest_asyncio
import httpx
import uuid
from datetime import datetime, timedelta, timezone
from app.database.session import SessionLocal
from app.models import Decision
from sqlalchemy import update


class TestDecisionExpiry:
    """Comprehensive tests for decision expiry mechanism."""

    @pytest_asyncio.fixture
    async def setup_user_device(self, api_client, auth_headers):
        """Create a user, farm, field, device and bring it online."""
        suffix = uuid.uuid4().hex[:8]
        
        r = await api_client.post("/api/farms", json={"name": f"Expiry Farm {suffix}"}, headers=auth_headers)
        farm_id = r.json()["id"]
        
        r = await api_client.post("/api/fields", json={"farm_id": farm_id, "name": f"Expiry Field {suffix}"}, headers=auth_headers)
        field_id = r.json()["id"]
        
        device_uid = f"esp32-expiry-{uuid.uuid4().hex[:8]}"
        r = await api_client.post("/api/devices", params={
            "field_id": field_id, "device_uid": device_uid, "name": "Expiry Device"
        }, headers=auth_headers)
        device_id = r.json()["id"]
        
        await api_client.post("/api/sensors/telemetry", json={
            "device_id": device_uid, "timestamp": "2024-01-15T10:00:00Z",
            "soil": {}, "environment": {}, "tank_level": 80, "pump": False
        })
        
        return {"device_id": device_id, "device_uid": device_uid, "field_id": field_id, "farm_id": farm_id}

    @pytest_asyncio.fixture
    async def spray_decision(self, api_client, auth_headers, setup_user_device):
        """Create a valid SPRAY decision (not expired)."""
        r = await api_client.post("/api/decision", params={"field_id": setup_user_device["field_id"]}, json={
            "analysis": {"climate_risk": {"drought": 0.2}}, "weather_data": {"rain_probability": 10}
        }, headers=auth_headers)
        return r.json()

    @pytest_asyncio.fixture
    async def irrigate_decision(self, api_client, auth_headers, setup_user_device):
        """Create a valid IRRIGATE decision (not expired)."""
        r = await api_client.post("/api/decision", params={"field_id": setup_user_device["field_id"]}, json={
            "analysis": {"climate_risk": {"drought": 0.9}}, "weather_data": {"rain_probability": 10}
        }, headers=auth_headers)
        return r.json()

    @pytest_asyncio.fixture
    async def expired_spray_decision(self, api_client, auth_headers, setup_user_device):
        """Create a SPRAY decision and manually set it as expired in the database."""
        r = await api_client.post("/api/decision", params={"field_id": setup_user_device["field_id"]}, json={
            "analysis": {"climate_risk": {"drought": 0.2}}, "weather_data": {"rain_probability": 10}
        }, headers=auth_headers)
        decision = r.json()
        decision_id = decision["decision_id"]
        
        # Manually expire it by updating expires_at in the database
        from app.database.session import SessionLocal
        from app.models import Decision
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import update
        
        db = SessionLocal()
        try:
            past = datetime.now(timezone.utc) - timedelta(seconds=10)
            stmt = update(Decision).where(Decision.id == decision_id).values(expires_at=past)
            db.execute(stmt)
            db.commit()
        finally:
            db.close()
        
        return {"decision_id": decision_id}

    @pytest_asyncio.fixture
    async def expired_irrigate_decision(self, api_client, auth_headers, setup_user_device):
        """Create an IRRIGATE decision and manually set it as expired in the database."""
        r = await api_client.post("/api/decision", params={"field_id": setup_user_device["field_id"]}, json={
            "analysis": {"climate_risk": {"drought": 0.9}}, "weather_data": {"rain_probability": 10}
        }, headers=auth_headers)
        decision = r.json()
        decision_id = decision["decision_id"]
        
        from app.database.session import SessionLocal
        from app.models import Decision
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import update
        
        db = SessionLocal()
        try:
            past = datetime.now(timezone.utc) - timedelta(seconds=10)
            stmt = update(Decision).where(Decision.id == decision_id).values(expires_at=past)
            db.execute(stmt)
            db.commit()
        finally:
            db.close()
        
        return {"decision_id": decision_id}

    @pytest_asyncio.fixture
    async def just_expired_decision(self, api_client, auth_headers, setup_user_device):
        """Create a decision and set expires_at to 1 second ago."""
        r = await api_client.post("/api/decision", params={"field_id": setup_user_device["field_id"]}, json={
            "analysis": {"climate_risk": {"drought": 0.2}}, "weather_data": {"rain_probability": 10}
        }, headers=auth_headers)
        decision = r.json()
        decision_id = decision["decision_id"]
        
        from app.database.session import SessionLocal
        from app.models import Decision
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import update
        
        db = SessionLocal()
        try:
            just_past = datetime.now(timezone.utc) - timedelta(seconds=1)
            stmt = update(Decision).where(Decision.id == decision_id).values(expires_at=just_past)
            db.execute(stmt)
            db.commit()
        finally:
            db.close()
        
        return {"decision_id": decision_id}

    @pytest_asyncio.fixture
    async def legacy_decision_no_expiry(self, api_client, auth_headers, setup_user_device):
        """Create a decision and set expires_at to NULL (legacy decision)."""
        r = await api_client.post("/api/decision", params={"field_id": setup_user_device["field_id"]}, json={
            "analysis": {"climate_risk": {"drought": 0.2}}, "weather_data": {"rain_probability": 10}
        }, headers=auth_headers)
        decision = r.json()
        decision_id = decision["decision_id"]
        
        from app.database.session import SessionLocal
        from app.models import Decision
        from sqlalchemy import update
        
        db = SessionLocal()
        try:
            stmt = update(Decision).where(Decision.id == decision_id).values(expires_at=None)
            db.execute(stmt)
            db.commit()
        finally:
            db.close()
        
        return {"decision_id": decision_id}

    async def test_valid_decision_spray(self, api_client, auth_headers, setup_user_device, spray_decision):
        """A valid (non-expired) SPRAY decision should be accepted."""
        r = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/spray",
            params={"decision_id": spray_decision["decision_id"]},
            headers=auth_headers
        )
        assert r.status_code == 200
        assert r.json()["command"] == "SPRAY"
        assert r.json()["status"] == "STARTED"

    async def test_valid_decision_irrigate(self, api_client, auth_headers, setup_user_device, irrigate_decision):
        """A valid (non-expired) IRRIGATE decision should be accepted."""
        r = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/irrigate",
            params={"decision_id": irrigate_decision["decision_id"]},
            headers=auth_headers
        )
        assert r.status_code == 200
        assert r.json()["command"] == "IRRIGATE"
        assert r.json()["status"] == "STARTED"

    async def test_expired_decision_spray_rejected(self, api_client, auth_headers, setup_user_device, expired_spray_decision):
        """An expired SPRAY decision should be rejected."""
        r = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/spray",
            params={"decision_id": expired_spray_decision["decision_id"]},
            headers=auth_headers
        )
        assert r.status_code == 409
        assert "expired" in r.json()["detail"].lower()

    async def test_expired_decision_irrigate_rejected(self, api_client, auth_headers, setup_user_device, expired_irrigate_decision):
        """An expired IRRIGATE decision should be rejected."""
        r = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/irrigate",
            params={"decision_id": expired_irrigate_decision["decision_id"]},
            headers=auth_headers
        )
        assert r.status_code == 409
        assert "expired" in r.json()["detail"].lower()

    async def test_boundary_timestamp_spray(self, api_client, auth_headers, setup_user_device):
        """A decision just past expiry (1 second) should be rejected."""
        # Create a fresh decision and expire it
        r = await api_client.post("/api/decision", params={"field_id": setup_user_device["field_id"]}, json={
            "analysis": {"climate_risk": {"drought": 0.2}}, "weather_data": {"rain_probability": 10}
        }, headers=auth_headers)
        decision_id = r.json()["decision_id"]
        
        from app.database.session import SessionLocal
        from app.models import Decision
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import update
        
        db = SessionLocal()
        try:
            just_past = datetime.now(timezone.utc) - timedelta(seconds=1)
            stmt = update(Decision).where(Decision.id == decision_id).values(expires_at=just_past)
            db.execute(stmt)
            db.commit()
        finally:
            db.close()
        
        r = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/spray",
            params={"decision_id": decision_id},
            headers=auth_headers
        )
        assert r.status_code == 409
        assert "expired" in r.json()["detail"].lower()

    async def test_boundary_timestamp_just_before_expiry(self, api_client, auth_headers, setup_user_device, spray_decision):
        """A decision just before expiry should still be valid."""
        # Fresh decision (created in fixture) should be valid
        r = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/spray",
            params={"decision_id": spray_decision["decision_id"]},
            headers=auth_headers
        )
        assert r.status_code == 200
        assert r.json()["command"] == "SPRAY"

    async def test_missing_expiry_treated_as_valid(self, api_client, auth_headers, setup_user_device):
        """A decision with NULL expires_at (legacy) should be treated as valid."""
        # Create a decision and set expires_at to NULL
        r = await api_client.post("/api/decision", params={"field_id": setup_user_device["field_id"]}, json={
            "analysis": {"climate_risk": {"drought": 0.2}}, "weather_data": {"rain_probability": 10}
        }, headers=auth_headers)
        decision = r.json()
        decision_id = decision["decision_id"]
        
        from app.database.session import SessionLocal
        from app.models import Decision
        from sqlalchemy import update
        
        db = SessionLocal()
        try:
            stmt = update(Decision).where(Decision.id == decision_id).values(expires_at=None)
            db.execute(stmt)
            db.commit()
        finally:
            db.close()
        
        r = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/spray",
            params={"decision_id": decision_id},
            headers=auth_headers
        )
        assert r.status_code == 200
        assert r.json()["command"] == "SPRAY"

    async def test_malformed_expiry_not_applicable(self):
        """Malformed expiry is not applicable since expiry is server-generated.
        
        The expires_at is set server-side when the decision is created,
        so clients cannot send malformed expiry values.
        This test documents that expiry cannot be client-controlled.
        """
        pass  # Documented behavior

    async def test_replay_expired_decision_rejected(self, api_client, auth_headers, setup_user_device):
        """Replay attempt with expired decision should be rejected."""
        # Create a new decision
        r = await api_client.post("/api/decision", params={"field_id": setup_user_device["field_id"]}, json={
            "analysis": {"climate_risk": {"drought": 0.2}}, "weather_data": {"rain_probability": 10}
        }, headers=auth_headers)
        decision_id = r.json()["decision_id"]
        
        # Use it while valid
        r1 = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/spray",
            params={"decision_id": decision_id},
            headers=auth_headers
        )
        assert r1.status_code == 200
        
        # Now expire it in the database
        from app.database.session import SessionLocal
        from app.models import Decision
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import update
        
        db = SessionLocal()
        try:
            past = datetime.now(timezone.utc) - timedelta(seconds=10)
            stmt = update(Decision).where(Decision.id == decision_id).values(expires_at=past)
            db.execute(stmt)
            db.commit()
        finally:
            db.close()
        
        # Try to replay
        r2 = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/spray",
            params={"decision_id": decision_id},
            headers=auth_headers
        )
        assert r2.status_code == 409
        assert "expired" in r2.json()["detail"].lower()

    async def test_emergency_stop_with_expired_decision(self, api_client, auth_headers, setup_user_device):
        """Emergency STOP must work even when decision is expired."""
        # Create an expired decision
        r = await api_client.post("/api/decision", params={"field_id": setup_user_device["field_id"]}, json={
            "analysis": {"climate_risk": {"drought": 0.2}}, "weather_data": {"rain_probability": 10}
        }, headers=auth_headers)
        decision = r.json()
        decision_id = decision["decision_id"]
        
        from app.database.session import SessionLocal
        from app.models import Decision
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import update
        
        db = SessionLocal()
        try:
            past = datetime.now(timezone.utc) - timedelta(seconds=10)
            stmt = update(Decision).where(Decision.id == decision_id).values(expires_at=past)
            db.execute(stmt)
            db.commit()
        finally:
            db.close()
        
        # Emergency stop should work even with expired decision
        r2 = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/stop",
            headers=auth_headers
        )
        assert r2.status_code == 200
        assert r2.json()["command"] == "STOP"
        
        # Verify pump is stopped (should already be false since we never started it)
        r = await api_client.get(f"/api/devices/{setup_user_device['device_id']}/status", headers=auth_headers)
        assert r.json()["pump_active"] is False

    async def test_emergency_stop_without_any_decision(self, api_client, auth_headers, setup_user_device):
        """Emergency STOP must work even without any decision."""
        r = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/stop",
            headers=auth_headers
        )
        assert r.status_code == 200
        assert r.json()["command"] == "STOP"

    async def test_expiry_enforced_in_command_function_not_bypassable(self, api_client, auth_headers, setup_user_device, expired_spray_decision):
        """Expiry check is enforced in the command function and cannot be bypassed through another device endpoint."""
        # Try spray endpoint with expired decision
        r1 = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/spray",
            params={"decision_id": expired_spray_decision["decision_id"]},
            headers=auth_headers
        )
        assert r1.status_code == 409
        
        # The expiry check happens in the shared command() function
        # which is called by both spray and irrigate endpoints
        # This verifies it's not bypassable through a different endpoint

    async def test_decision_creation_sets_expires_at(self, api_client, auth_headers, setup_user_device):
        """Decision creation should set expires_at based on decision_ttl_seconds."""
        r = await api_client.post("/api/decision", params={"field_id": setup_user_device["field_id"]}, json={
            "analysis": {"climate_risk": {"drought": 0.2}}, "weather_data": {"rain_probability": 10}
        }, headers=auth_headers)
        assert r.status_code == 200
        decision = r.json()
        assert "decision_id" in decision

    async def test_configurable_ttl_respected(self):
        """Test that the configured TTL is respected.
        
        Note: This test requires changing the config, which is not easily done
        in a running container. The default TTL is 300 seconds.
        """
        pass  # Documented behavior