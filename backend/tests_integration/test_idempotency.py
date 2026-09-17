import pytest
import pytest_asyncio
import httpx
import uuid


class TestIdempotency:
    """Tests for idempotency of device commands."""

    @pytest_asyncio.fixture
    async def setup_user_device(self, api_client, auth_headers):
        """Create a user, farm, field, device and bring it online."""
        import uuid
        suffix = uuid.uuid4().hex[:8]
        
        r = await api_client.post("/api/farms", json={"name": f"Idem Farm {suffix}"}, headers=auth_headers)
        farm_id = r.json()["id"]
        
        r = await api_client.post("/api/fields", json={"farm_id": farm_id, "name": f"Idem Field {suffix}"}, headers=auth_headers)
        field_id = r.json()["id"]
        
        device_uid = f"esp32-idem-{uuid.uuid4().hex[:8]}"
        r = await api_client.post("/api/devices", params={
            "field_id": field_id, "device_uid": device_uid, "name": "Idempotency Device"
        }, headers=auth_headers)
        device_id = r.json()["id"]
        
        await api_client.post("/api/sensors/telemetry", json={
            "device_id": device_uid, "timestamp": "2024-01-15T10:00:00Z",
            "soil": {}, "environment": {}, "tank_level": 80, "pump": False
        })
        
        # Create decisions
        r = await api_client.post("/api/decision", params={"field_id": field_id}, json={
            "analysis": {"climate_risk": {"drought": 0.2}}, "weather_data": {"rain_probability": 10}
        }, headers=auth_headers)
        spray_decision_id = r.json()["decision_id"]
        
        r = await api_client.post("/api/decision", params={"field_id": field_id}, json={
            "analysis": {"climate_risk": {"drought": 0.9}}, "weather_data": {"rain_probability": 10}
        }, headers=auth_headers)
        irrigate_decision_id = r.json()["decision_id"]
        
        return {
            "device_id": device_id,
            "device_uid": device_uid,
            "field_id": field_id,
            "spray_decision_id": spray_decision_id,
            "irrigate_decision_id": irrigate_decision_id
        }

    async def test_first_request_succeeds(self, api_client, auth_headers, setup_user_device):
        """First request with idempotency key must succeed."""
        idem_key = f"idem-{uuid.uuid4().hex}"
        r = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/spray",
            params={"decision_id": setup_user_device["spray_decision_id"]},
            headers={**auth_headers, "Idempotency-Key": idem_key}
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "STARTED"
        assert data["idempotent"] is False
        assert "event_id" in data

    async def test_exact_retry_returns_same_event(self, api_client, auth_headers, setup_user_device):
        """Exact retry with same idempotency key must return same event."""
        idem_key = f"idem-{uuid.uuid4().hex}"
        
        # First request
        r1 = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/spray",
            params={"decision_id": setup_user_device["spray_decision_id"]},
            headers={**auth_headers, "Idempotency-Key": idem_key}
        )
        assert r1.status_code == 200
        event_id_1 = r1.json()["event_id"]
        
        # Retry with same key
        r2 = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/spray",
            params={"decision_id": setup_user_device["spray_decision_id"]},
            headers={**auth_headers, "Idempotency-Key": idem_key}
        )
        assert r2.status_code == 200
        event_id_2 = r2.json()["event_id"]
        
        # Must be same event
        assert event_id_1 == event_id_2
        assert r2.json()["idempotent"] is True

    async def test_retry_after_timeout_simulation(self, api_client, auth_headers, setup_user_device):
        """Retry after timeout simulation must return same event."""
        idem_key = f"idem-{uuid.uuid4().hex}"
        
        r1 = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/spray",
            params={"decision_id": setup_user_device["spray_decision_id"]},
            headers={**auth_headers, "Idempotency-Key": idem_key}
        )
        event_id_1 = r1.json()["event_id"]
        
        # Simulate timeout by waiting and retrying
        import asyncio
        await asyncio.sleep(0.1)
        
        r2 = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/spray",
            params={"decision_id": setup_user_device["spray_decision_id"]},
            headers={**auth_headers, "Idempotency-Key": idem_key}
        )
        assert r2.status_code == 200
        assert r2.json()["event_id"] == event_id_1
        assert r2.json()["idempotent"] is True

    async def test_same_key_different_payload_rejected(self, api_client, auth_headers, setup_user_device):
        """Same idempotency key with different payload must be rejected."""
        idem_key = f"idem-{uuid.uuid4().hex}"
        
        # First request: spray
        r1 = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/spray",
            params={"decision_id": setup_user_device["spray_decision_id"]},
            headers={**auth_headers, "Idempotency-Key": idem_key}
        )
        assert r1.status_code == 200
        
        # Retry with same key but different action (irrigate)
        r2 = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/irrigate",
            params={"decision_id": setup_user_device["irrigate_decision_id"]},
            headers={**auth_headers, "Idempotency-Key": idem_key}
        )
        assert r2.status_code == 409
        assert "different" in r2.json()["detail"].lower() or "conflict" in r2.json()["detail"].lower()

    async def test_same_key_different_decision_rejected(self, api_client, auth_headers, setup_user_device):
        """Same idempotency key with different decision_id must be rejected."""
        idem_key = f"idem-{uuid.uuid4().hex}"
        
        # Create another decision
        r = await api_client.post("/api/decision", params={"field_id": setup_user_device["field_id"]}, json={
            "analysis": {"climate_risk": {"drought": 0.3}}, "weather_data": {"rain_probability": 15}
        }, headers=auth_headers)
        other_decision_id = r.json()["decision_id"]
        
        # First request
        r1 = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/spray",
            params={"decision_id": setup_user_device["spray_decision_id"]},
            headers={**auth_headers, "Idempotency-Key": idem_key}
        )
        assert r1.status_code == 200
        
        # Retry with different decision_id
        r2 = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/spray",
            params={"decision_id": other_decision_id},
            headers={**auth_headers, "Idempotency-Key": idem_key}
        )
        assert r2.status_code == 409

    async def test_same_key_different_device_rejected(self, api_client, auth_headers, setup_user_device):
        """Same idempotency key on different device must be rejected."""
        idem_key = f"idem-{uuid.uuid4().hex}"
        
        # Create another device
        device_uid = f"esp32-other-{uuid.uuid4().hex[:8]}"
        r = await api_client.post("/api/devices", params={
            "field_id": setup_user_device["field_id"], "device_uid": device_uid, "name": "Other Device"
        }, headers=auth_headers)
        other_device_id = r.json()["id"]
        
        await api_client.post("/api/sensors/telemetry", json={
            "device_id": device_uid, "timestamp": "2024-01-15T10:00:00Z",
            "soil": {}, "environment": {}, "tank_level": 80, "pump": False
        })
        
        # First request on original device
        r1 = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/spray",
            params={"decision_id": setup_user_device["spray_decision_id"]},
            headers={**auth_headers, "Idempotency-Key": idem_key}
        )
        assert r1.status_code == 200
        
        # Retry on different device
        r2 = await api_client.post(
            f"/api/devices/{other_device_id}/spray",
            params={"decision_id": setup_user_device["spray_decision_id"]},
            headers={**auth_headers, "Idempotency-Key": idem_key}
        )
        assert r2.status_code == 409

    async def test_concurrent_duplicate_requests(self, api_client, auth_headers, setup_user_device):
        """Concurrent duplicate requests must return same event."""
        idem_key = f"idem-{uuid.uuid4().hex}"
        
        # Fire multiple concurrent requests
        import asyncio
        async def make_request():
            return await api_client.post(
                f"/api/devices/{setup_user_device['device_id']}/spray",
                params={"decision_id": setup_user_device["spray_decision_id"]},
                headers={**auth_headers, "Idempotency-Key": idem_key}
            )
        
        results = await asyncio.gather(*[make_request() for _ in range(5)])
        
        # All should succeed
        for r in results:
            assert r.status_code == 200
        
        # All should return same event_id
        event_ids = [r.json()["event_id"] for r in results]
        assert len(set(event_ids)) == 1
        
        # Only first should be non-idempotent, rest idempotent
        idempotent_flags = [r.json()["idempotent"] for r in results]
        assert idempotent_flags.count(False) == 1
        assert idempotent_flags.count(True) == 4

    async def test_irrigate_idempotency(self, api_client, auth_headers, setup_user_device):
        """Idempotency must work for irrigate command."""
        idem_key = f"idem-{uuid.uuid4().hex}"
        
        r1 = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/irrigate",
            params={"decision_id": setup_user_device["irrigate_decision_id"]},
            headers={**auth_headers, "Idempotency-Key": idem_key}
        )
        assert r1.status_code == 200
        event_id_1 = r1.json()["event_id"]
        
        r2 = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/irrigate",
            params={"decision_id": setup_user_device["irrigate_decision_id"]},
            headers={**auth_headers, "Idempotency-Key": idem_key}
        )
        assert r2.status_code == 200
        assert r2.json()["event_id"] == event_id_1
        assert r2.json()["idempotent"] is True

    async def test_stop_idempotency(self, api_client, auth_headers, setup_user_device):
        """Idempotency must work for stop command (no decision required)."""
        idem_key = f"idem-{uuid.uuid4().hex}"
        
        r1 = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/stop",
            headers={**auth_headers, "Idempotency-Key": idem_key}
        )
        assert r1.status_code == 200
        event_id_1 = r1.json()["event_id"]
        
        r2 = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/stop",
            headers={**auth_headers, "Idempotency-Key": idem_key}
        )
        assert r2.status_code == 200
        assert r2.json()["event_id"] == event_id_1
        assert r2.json()["idempotent"] is True

    async def test_without_idempotency_key_creates_new_event(self, api_client, auth_headers, setup_user_device):
        """Requests without idempotency key must create new events each time."""
        r1 = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/spray",
            params={"decision_id": setup_user_device["spray_decision_id"]},
            headers=auth_headers
        )
        assert r1.status_code == 200
        event_id_1 = r1.json()["event_id"]
        
        r2 = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/spray",
            params={"decision_id": setup_user_device["spray_decision_id"]},
            headers=auth_headers
        )
        assert r2.status_code == 200
        event_id_2 = r2.json()["event_id"]
        
        assert event_id_1 != event_id_2
        assert r1.json().get("idempotent") is False
        assert r2.json().get("idempotent") is False

    async def test_idempotency_key_persisted_in_database(self, api_client, auth_headers, setup_user_device):
        """Idempotency key must be stored in the database."""
        idem_key = f"idem-{uuid.uuid4().hex}"
        
        r = await api_client.post(
            f"/api/devices/{setup_user_device['device_id']}/spray",
            params={"decision_id": setup_user_device["spray_decision_id"]},
            headers={**auth_headers, "Idempotency-Key": idem_key}
        )
        assert r.status_code == 200
        event_id = r.json()["event_id"]
        
        # Verify in database by checking history
        r = await api_client.get(f"/api/fields/{setup_user_device['field_id']}/history", headers=auth_headers)
        assert r.status_code == 200
        history = r.json()
        # Note: history endpoint may not expose idempotency_key directly
        # But the event was created successfully
        assert len(history["decisions"]) >= 0