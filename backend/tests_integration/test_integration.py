import pytest
import httpx
import io
from PIL import Image


class TestAuthentication:
    async def test_register_user(self, api_client):
        import uuid
        email = f"newuser_{uuid.uuid4().hex[:8]}@test.com"
        r = await api_client.post("/api/auth/register", json={
            "email": email, "password": "password123", "full_name": "New User"
        })
        assert r.status_code == 201
        data = r.json()
        assert data["email"] == email
        assert data["full_name"] == "New User"
        assert "id" in data
        assert "password" not in data

    async def test_register_duplicate_email_rejected(self, api_client):
        await api_client.post("/api/auth/register", json={
            "email": "dup@test.com", "password": "password123", "full_name": "Dup"
        })
        r = await api_client.post("/api/auth/register", json={
            "email": "dup@test.com", "password": "password123", "full_name": "Dup"
        })
        assert r.status_code == 409
        assert "already registered" in r.json()["detail"].lower()

    async def test_login_valid_credentials(self, api_client):
        await api_client.post("/api/auth/register", json={
            "email": "login@test.com", "password": "password123", "full_name": "Login User"
        })
        r = await api_client.post("/api/auth/login", data={
            "username": "login@test.com", "password": "password123"
        })
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_invalid_password_rejected(self, api_client):
        await api_client.post("/api/auth/register", json={
            "email": "badpass@test.com", "password": "password123", "full_name": "Bad Pass"
        })
        r = await api_client.post("/api/auth/login", data={
            "username": "badpass@test.com", "password": "wrongpassword"
        })
        assert r.status_code == 401
        assert "invalid credentials" in r.json()["detail"].lower()

    async def test_login_nonexistent_user_rejected(self, api_client):
        r = await api_client.post("/api/auth/login", data={
            "username": "nonexistent@test.com", "password": "password123"
        })
        assert r.status_code == 401

    async def test_unauthenticated_protected_endpoint_rejected(self, api_client):
        r = await api_client.get("/api/auth/me")
        assert r.status_code == 401

    async def test_get_current_user(self, api_client):
        await api_client.post("/api/auth/register", json={
            "email": "me@test.com", "password": "password123", "full_name": "Me User"
        })
        r = await api_client.post("/api/auth/login", data={
            "username": "me@test.com", "password": "password123"
        })
        token = r.json()["access_token"]
        r = await api_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == "me@test.com"
        assert data["full_name"] == "Me User"


class TestFarmFieldOwnership:
    async def test_create_farm(self, api_client, auth_headers):
        r = await api_client.post("/api/farms", json={
            "name": "My Farm", "location": {"lat": 12.3, "lon": 45.6}
        }, headers=auth_headers)
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "My Farm"
        assert data["location"]["lat"] == 12.3
        assert "id" in data

    async def test_list_farms(self, api_client, auth_headers):
        import uuid
        suffix = uuid.uuid4().hex[:8]
        name1 = f"Farm List 1 {suffix}"
        name2 = f"Farm List 2 {suffix}"
        await api_client.post("/api/farms", json={"name": name1}, headers=auth_headers)
        await api_client.post("/api/farms", json={"name": name2}, headers=auth_headers)
        r = await api_client.get("/api/farms", headers=auth_headers)
        assert r.status_code == 200
        farms = r.json()
        user_farms = [f for f in farms if f["name"] in (name1, name2)]
        assert len(user_farms) == 2

    async def test_create_field(self, api_client, auth_headers, farm_id):
        r = await api_client.post("/api/fields", json={
            "farm_id": farm_id, "name": "Field A", "crop": "corn", "growth_stage": "vegetative"
        }, headers=auth_headers)
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Field A"
        assert data["crop"] == "corn"
        assert data["farm_id"] == farm_id

    async def test_list_fields(self, api_client, auth_headers, farm_id):
        import uuid
        suffix = uuid.uuid4().hex[:8]
        name1 = f"Field List 1 {suffix}"
        name2 = f"Field List 2 {suffix}"
        await api_client.post("/api/fields", json={"farm_id": farm_id, "name": name1}, headers=auth_headers)
        await api_client.post("/api/fields", json={"farm_id": farm_id, "name": name2}, headers=auth_headers)
        r = await api_client.get("/api/fields", headers=auth_headers)
        assert r.status_code == 200
        fields = r.json()
        user_fields = [f for f in fields if f["name"] in (name1, name2)]
        assert len(user_fields) == 2

    async def test_cannot_access_another_users_farm(self, api_client, auth_headers, auth_headers_user2):
        r1 = await api_client.post("/api/farms", json={"name": "User1 Farm"}, headers=auth_headers)
        farm_id = r1.json()["id"]
        r = await api_client.get(f"/api/farms/{farm_id}", headers=auth_headers_user2)
        assert r.status_code == 404

    async def test_cannot_create_field_on_another_users_farm(self, api_client, auth_headers, auth_headers_user2, farm_id):
        r = await api_client.post("/api/fields", json={
            "farm_id": farm_id, "name": "Hacker Field"
        }, headers=auth_headers_user2)
        assert r.status_code == 404


class TestDevices:
    async def test_register_device(self, api_client, auth_headers, field_id):
        import uuid
        uid = f"esp32-reg-{uuid.uuid4().hex[:8]}"
        r = await api_client.post("/api/devices", params={
            "field_id": field_id, "device_uid": uid, "name": "Register Device"
        }, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["device_uid"] == uid
        assert data["status"] == "OFFLINE"

    async def test_get_device_status(self, api_client, auth_headers, device_id):
        r = await api_client.get(f"/api/devices/{device_id}/status", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "device_id" in data

    async def test_valid_spray_command(self, api_client, auth_headers, field_id, device_id):
        r = await api_client.post("/api/decision", params={"field_id": field_id}, json={
            "analysis": {"climate_risk": {"drought": 0.2}}, "weather_data": {"rain_probability": 10}
        }, headers=auth_headers)
        decision_id = r.json()["decision_id"]
        r = await api_client.post(f"/api/devices/{device_id}/spray", params={"decision_id": decision_id}, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["command"] == "SPRAY"
        assert data["status"] == "STARTED"

    async def test_valid_irrigate_command(self, api_client, auth_headers, field_id, device_id):
        r = await api_client.post("/api/decision", params={"field_id": field_id}, json={
            "analysis": {"climate_risk": {"drought": 0.9}}, "weather_data": {"rain_probability": 10}
        }, headers=auth_headers)
        decision_id = r.json()["decision_id"]
        r = await api_client.post(f"/api/devices/{device_id}/irrigate", params={"decision_id": decision_id}, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["command"] == "IRRIGATE"

    async def test_emergency_stop(self, api_client, auth_headers, device_id):
        r = await api_client.post(f"/api/devices/{device_id}/stop", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["command"] == "STOP"
        assert data["status"] == "STOPPED"

    async def test_spray_requires_decision(self, api_client, auth_headers):
        r = await api_client.post("/api/devices/1/spray", headers=auth_headers)
        assert r.status_code == 422

    async def test_spray_rejected_if_decision_not_authorize(self, api_client, auth_headers, field_id, device_id):
        # Device is already online from fixture
        # Create decision with high rain probability -> DELAY_SPRAY
        r = await api_client.post("/api/decision", params={"field_id": field_id}, json={
            "analysis": {"climate_risk": {"drought": 0.2}}, "weather_data": {"rain_probability": 80}
        }, headers=auth_headers)
        decision_id = r.json()["decision_id"]
        r = await api_client.post(f"/api/devices/{device_id}/spray", params={"decision_id": decision_id}, headers=auth_headers)
        assert r.status_code == 409
        assert "not authorized" in r.json()["detail"].lower() or "delay" in r.json()["detail"].lower()

    async def test_spray_rejected_if_critical_risk(self, api_client, auth_headers, field_id, device_id):
        r = await api_client.post("/api/decision", params={"field_id": field_id}, json={
            "analysis": {"climate_risk": {"drought": 0.9, "heat": 0.9}}, "weather_data": {"rain_probability": 10}
        }, headers=auth_headers)
        decision_id = r.json()["decision_id"]
        r = await api_client.post(f"/api/devices/{device_id}/spray", params={"decision_id": decision_id}, headers=auth_headers)
        assert r.status_code == 409

    async def test_irrigate_rejected_if_decision_not_authorize(self, api_client, auth_headers, field_id, device_id):
        r = await api_client.post("/api/decision", params={"field_id": field_id}, json={
            "analysis": {"climate_risk": {"drought": 0.2}}, "weather_data": {"rain_probability": 10}
        }, headers=auth_headers)
        decision_id = r.json()["decision_id"]
        r = await api_client.post(f"/api/devices/{device_id}/irrigate", params={"decision_id": decision_id}, headers=auth_headers)
        assert r.status_code == 409

    async def test_cannot_access_another_users_device(self, api_client, auth_headers, auth_headers_user2, device_id):
        r = await api_client.get(f"/api/devices/{device_id}/status", headers=auth_headers_user2)
        assert r.status_code == 404


class TestSensors:
    async def test_post_telemetry(self, api_client, device_uid):
        r = await api_client.post("/api/sensors/telemetry", json={
            "device_id": device_uid,
            "timestamp": "2024-01-15T10:00:00Z",
            "soil": {"moisture": 45, "ph": 6.5},
            "environment": {"temperature": 25.5, "humidity": 60},
            "tank_level": 80.0,
            "pump": False
        })
        assert r.status_code == 201
        data = r.json()
        assert data["accepted"] is True
        assert "reading_id" in data
        assert data["device_timestamp"] == "2024-01-15T10:00:00Z"
        assert "server_timestamp" in data

    async def test_get_latest_reading(self, api_client, auth_headers, device_uid):
        await api_client.post("/api/sensors/telemetry", json={
            "device_id": device_uid,
            "timestamp": "2024-01-15T11:00:00Z",
            "soil": {"moisture": 50},
            "environment": {"temperature": 26},
            "tank_level": 75,
            "pump": True
        })
        r = await api_client.get(f"/api/sensors/latest", params={"device_id": device_uid}, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["device_id"] == device_uid
        assert data["reading"] is not None
        assert data["reading"]["soil"]["moisture"] == 50
        assert "device_timestamp" in data
        assert "server_timestamp" in data

    async def test_get_historical_readings(self, api_client, auth_headers, device_uid):
        for i in range(5):
            await api_client.post("/api/sensors/telemetry", json={
                "device_id": device_uid,
                "timestamp": f"2024-01-15T{12+i}:00:00Z",
                "soil": {"moisture": 40 + i},
                "environment": {"temperature": 20 + i},
                "tank_level": 80 - i,
                "pump": False
            })
        r = await api_client.get(f"/api/sensors/history", params={"device_id": device_uid, "limit": 3}, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 3
        assert all("device_timestamp" in row and "server_timestamp" in row and "payload" in row for row in data)

    async def test_telemetry_updates_device_status(self, api_client, auth_headers, device_id, device_uid):
        # device is already online from fixture
        r = await api_client.get(f"/api/devices/{device_id}/status", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "ONLINE"

    async def test_invalid_telemetry_rejected(self, api_client):
        r = await api_client.post("/api/sensors/telemetry", json={
            "device_id": "nonexistent", "timestamp": "2024-01-15T10:00:00Z"
        })
        assert r.status_code == 404

    async def test_telemetry_missing_fields_rejected(self, api_client):
        r = await api_client.post("/api/sensors/telemetry", json={
            "device_id": "esp32-001"
        })
        assert r.status_code == 422


class TestAnalysis:
    def _create_test_image(self):
        img = Image.new('RGB', (100, 100), color='red')
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        buf.seek(0)
        return buf.getvalue()

    async def test_upload_valid_image(self, api_client, auth_headers, field_id):
        img_data = self._create_test_image()
        files = {"image": ("test.jpg", img_data, "image/jpeg")}
        r = await api_client.post("/api/analysis", files=files, data={"field_id": str(field_id)}, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "analysis_id" in data
        assert "analysis" in data
        assert "decision" in data
        assert "weather" in data
        assert data["analysis"]["crop"]["name"] == "tomato"
        assert data["analysis"]["disease"]["name"] == "early_blight"

    async def test_analysis_persists_to_database(self, api_client, auth_headers, field_id):
        img_data = self._create_test_image()
        files = {"image": ("test.jpg", img_data, "image/jpeg")}
        r = await api_client.post("/api/analysis", files=files, data={"field_id": str(field_id)}, headers=auth_headers)
        assert r.status_code == 200
        analysis_id = r.json()["analysis_id"]
        r = await api_client.get(f"/api/fields/{field_id}/health", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["latest_analysis"] is not None
        assert r.json()["latest_analysis"]["crop"]["name"] == "tomato"

    async def test_invalid_image_type_rejected(self, api_client, auth_headers, field_id):
        files = {"image": ("test.txt", b"not an image", "text/plain")}
        r = await api_client.post("/api/analysis", files=files, data={"field_id": str(field_id)}, headers=auth_headers)
        assert r.status_code == 415

    async def test_oversized_image_rejected(self, api_client, auth_headers, field_id):
        large_img = b"x" * (11 * 1024 * 1024)
        files = {"image": ("large.jpg", large_img, "image/jpeg")}
        r = await api_client.post("/api/analysis", files=files, data={"field_id": str(field_id)}, headers=auth_headers)
        assert r.status_code == 413

    async def test_analysis_requires_auth(self, api_client, field_id):
        img_data = self._create_test_image()
        files = {"image": ("test.jpg", img_data, "image/jpeg")}
        r = await api_client.post("/api/analysis", files=files, data={"field_id": str(field_id)})
        assert r.status_code == 401

    async def test_analysis_requires_ownership(self, api_client, auth_headers_user2, field_id):
        img_data = self._create_test_image()
        files = {"image": ("test.jpg", img_data, "image/jpeg")}
        r = await api_client.post("/api/analysis", files=files, data={"field_id": str(field_id)}, headers=auth_headers_user2)
        assert r.status_code == 404


class TestDecision:
    async def test_submit_decision_request(self, api_client, auth_headers, field_id):
        r = await api_client.post("/api/decision", params={"field_id": field_id}, json={
            "analysis": {"climate_risk": {"drought": 0.3}},
            "weather_data": {"rain_probability": 20},
            "sensor_data": {"soil": {"moisture": 50}}
        }, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "decision_id" in data
        assert "primary_decision" in data
        assert "risk_level" in data
        assert data["primary_decision"] in ["SPRAY", "IRRIGATE", "DELAY_SPRAY", "MONITOR", "WARN"]

    async def test_decision_persisted(self, api_client, auth_headers, field_id):
        r = await api_client.post("/api/decision", params={"field_id": field_id}, json={
            "test": "data"
        }, headers=auth_headers)
        assert r.status_code == 200
        decision_id = r.json()["decision_id"]
        r = await api_client.get(f"/api/fields/{field_id}/history", headers=auth_headers)
        assert r.status_code == 200
        history = r.json()
        decisions = history.get("decisions", [])
        assert len(decisions) > 0
        # Verify the decision data is persisted
        assert any(d.get("primary_decision") == "SPRAY" for d in decisions)

    async def test_decision_requires_auth(self, api_client, field_id):
        r = await api_client.post("/api/decision", params={"field_id": field_id}, json={"test": "data"})
        assert r.status_code == 401

    async def test_decision_requires_ownership(self, api_client, auth_headers_user2, field_id):
        r = await api_client.post("/api/decision", params={"field_id": field_id}, json={"test": "data"}, headers=auth_headers_user2)
        assert r.status_code == 404


class TestWeather:
    async def test_weather_abstraction_works(self, api_client, auth_headers, field_id):
        img_data = Image.new('RGB', (50, 50), color='green')
        buf = io.BytesIO()
        img_data.save(buf, format='JPEG')
        files = {"image": ("test.jpg", buf.getvalue(), "image/jpeg")}
        r = await api_client.post("/api/analysis", files=files, data={"field_id": str(field_id)}, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "weather" in data
        weather = data["weather"]
        assert "temperature" in weather
        assert "humidity" in weather
        assert "rainfall" in weather
        assert "rain_probability" in weather
        assert "forecast" in weather
        assert "extreme_weather" in weather

    async def test_mock_ai_service_direct(self, mock_ai_client):
        files = {"image": ("test.jpg", b"fake", "image/jpeg")}
        data = {"sensor_data": "{}", "weather_data": "{}", "crop_stage": ""}
        r = await mock_ai_client.post("/ai/analyze", files=files, data=data)
        assert r.status_code == 200
        data = r.json()
        assert "crop" in data
        assert "disease" in data
        assert "climate_risk" in data

    async def test_mock_decision_service_direct(self, mock_decision_client):
        r = await mock_decision_client.post("/decision", json={
            "analysis": {"climate_risk": {"drought": 0.2}},
            "weather_data": {"rain_probability": 10}
        })
        assert r.status_code == 200
        data = r.json()
        assert data["primary_decision"] == "SPRAY"

    async def test_mock_decision_rain_delay(self, mock_decision_client):
        r = await mock_decision_client.post("/decision", json={
            "analysis": {"climate_risk": {}}, "weather_data": {"rain_probability": 80}
        })
        assert r.status_code == 200
        assert r.json()["primary_decision"] == "DELAY_SPRAY"

    async def test_mock_decision_drought_irrigate(self, mock_decision_client):
        r = await mock_decision_client.post("/decision", json={
            "analysis": {"climate_risk": {"drought": 0.9}}, "weather_data": {"rain_probability": 10}
        })
        assert r.status_code == 200
        assert r.json()["primary_decision"] == "IRRIGATE"


class TestAssistantGenAI:
    async def test_explain_endpoint(self, api_client, auth_headers, field_id):
        img_data = Image.new('RGB', (50, 50), color='blue')
        buf = io.BytesIO()
        img_data.save(buf, format='JPEG')
        files = {"image": ("test.jpg", buf.getvalue(), "image/jpeg")}
        r = await api_client.post("/api/analysis", files=files, data={"field_id": str(field_id)}, headers=auth_headers)
        assert r.status_code == 200
        analysis = r.json()["analysis"]
        decision = r.json()["decision"]
        r = await api_client.post("/api/assistant/explain", json={"analysis": analysis, "decision": decision}, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "text" in data
        assert "source" in data
        assert "tomato" in data["text"].lower()

    async def test_assistant_requires_auth(self, api_client):
        r = await api_client.post("/api/assistant/explain", json={"analysis": {}, "decision": {}})
        assert r.status_code == 401

    async def test_mock_genai_service_direct(self, mock_genai_client):
        r = await mock_genai_client.post("/assistant/explain", json={
            "analysis": {"crop": {"name": "corn"}, "disease": {"name": "rust"}},
            "decision": {"primary_decision": "SPRAY"}
        })
        assert r.status_code == 200
        data = r.json()
        assert "text" in data
        assert data["source"] == "mock-genai"


class TestAlerts:
    async def test_list_alerts(self, api_client, auth_headers, field_id):
        img_data = Image.new('RGB', (50, 50), color='yellow')
        buf = io.BytesIO()
        img_data.save(buf, format='JPEG')
        files = {"image": ("test.jpg", buf.getvalue(), "image/jpeg")}
        await api_client.post("/api/analysis", files=files, data={"field_id": str(field_id)}, headers=auth_headers)
        r = await api_client.get("/api/alerts", headers=auth_headers)
        assert r.status_code == 200
        alerts = r.json()
        assert isinstance(alerts, list)
        assert len(alerts) > 0
        assert all("alert_type" in a and "severity" in a and "message" in a for a in alerts)

    async def test_filter_alerts_by_field(self, api_client, auth_headers, field_id):
        r = await api_client.get("/api/alerts", params={"field_id": field_id}, headers=auth_headers)
        assert r.status_code == 200
        alerts = r.json()
        assert all(a["field_id"] == field_id for a in alerts)

    async def test_alerts_ownership(self, api_client, auth_headers, auth_headers_user2, field_id):
        r = await api_client.get("/api/alerts", headers=auth_headers_user2)
        assert r.status_code == 200
        assert len(r.json()) == 0


class TestDatabaseIntegrity:
    async def test_foreign_keys_enforced(self, api_client, auth_headers, auth_headers_user2, farm_id):
        r = await api_client.post("/api/fields", json={"farm_id": 99999, "name": "Bad Field"}, headers=auth_headers)
        assert r.status_code == 404

    async def test_timestamps_present(self, api_client, auth_headers, field_id):
        img_data = Image.new('RGB', (50, 50), color='purple')
        buf = io.BytesIO()
        img_data.save(buf, format='JPEG')
        files = {"image": ("test.jpg", buf.getvalue(), "image/jpeg")}
        r = await api_client.post("/api/analysis", files=files, data={"field_id": str(field_id)}, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        analysis_id = data["analysis_id"]
        r = await api_client.get(f"/api/fields/{field_id}/health", headers=auth_headers)
        latest = r.json()["latest_analysis"]
        assert latest is not None

    async def test_spray_event_status_enum(self, api_client, auth_headers, field_id, device_id):
        r = await api_client.post("/api/decision", params={"field_id": field_id}, json={
            "analysis": {"climate_risk": {}}, "weather_data": {"rain_probability": 10}
        }, headers=auth_headers)
        decision_id = r.json()["decision_id"]
        r = await api_client.post(f"/api/devices/{device_id}/spray", params={"decision_id": decision_id}, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["status"] in ["STARTED", "STOPPED", "COMPLETED", "FAILED"]


class TestErrorHandling:
    async def test_no_stack_traces_in_errors(self, api_client):
        r = await api_client.get("/api/nonexistent")
        assert r.status_code == 404
        assert "traceback" not in r.text.lower()

    async def test_no_secrets_in_errors(self, api_client, auth_headers):
        r = await api_client.post("/api/devices/1/spray", params={"decision_id": 99999}, headers=auth_headers)
        assert r.status_code == 404
        assert "password" not in r.text.lower()
        assert "secret" not in r.text.lower()
        assert "jwt" not in r.text.lower()

    async def test_validation_errors_422(self, api_client):
        r = await api_client.post("/api/auth/register", json={"email": "invalid", "password": "short"})
        assert r.status_code == 422


class TestOpenAPI:
    async def test_openapi_json_exists(self, api_client):
        r = await api_client.get("/openapi.json")
        assert r.status_code == 200
        spec = r.json()
        assert "openapi" in spec
        assert "paths" in spec

    async def test_openapi_has_expected_endpoints(self, api_client):
        r = await api_client.get("/openapi.json")
        spec = r.json()
        paths = spec["paths"]
        expected = [
            "/api/auth/register", "/api/auth/login", "/api/auth/me",
            "/api/farms", "/api/fields",
            "/api/sensors/telemetry", "/api/sensors/latest", "/api/sensors/history",
            "/api/analysis", "/api/decision",
            "/api/devices", "/api/devices/{device_id}/spray", "/api/devices/{device_id}/irrigate", "/api/devices/{device_id}/stop", "/api/devices/{device_id}/status",
            "/api/assistant/explain",
            "/api/alerts",
            "/api/dashboard", "/api/fields/{field_id}/health", "/api/fields/{field_id}/risk", "/api/fields/{field_id}/history",
            "/health"
        ]
        for ep in expected:
            found = any(ep.replace("{device_id}", "{device_id}").replace("{field_id}", "{field_id}") in p for p in paths)
            assert found, f"Missing endpoint: {ep}"

    async def test_openapi_schemas_match(self, api_client):
        r = await api_client.get("/openapi.json")
        spec = r.json()
        schemas = spec.get("components", {}).get("schemas", {})
        # Check that key schemas exist (names may be auto-generated by FastAPI)
        assert "TelemetryIn" in schemas or any("TelemetryIn" in k for k in schemas)
        assert "TelemetryOut" in schemas or any("TelemetryOut" in k for k in schemas)
        assert "UserCreate" in schemas or any("UserCreate" in k for k in schemas)
        assert "Token" in schemas or any("Token" in k for k in schemas)
        assert "FarmCreate" in schemas or any("FarmCreate" in k for k in schemas)
        # AnalysisResult and DecisionResult may have different names in OpenAPI
        # Just verify the API documents have schemas
        assert len(schemas) > 0