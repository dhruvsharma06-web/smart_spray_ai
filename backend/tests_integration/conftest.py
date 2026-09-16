import pytest
import pytest_asyncio
import httpx


@pytest_asyncio.fixture
async def api_client():
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        yield client


@pytest_asyncio.fixture
async def mock_ai_client():
    async with httpx.AsyncClient(base_url="http://mock-ai:8001", timeout=30.0) as client:
        yield client


@pytest_asyncio.fixture
async def mock_decision_client():
    async with httpx.AsyncClient(base_url="http://mock-decision:8002", timeout=30.0) as client:
        yield client


@pytest_asyncio.fixture
async def real_decision_client():
    async with httpx.AsyncClient(base_url="http://decision:8002", timeout=30.0) as client:
        yield client


@pytest_asyncio.fixture
async def mock_genai_client():
    async with httpx.AsyncClient(base_url="http://mock-genai:8003", timeout=30.0) as client:
        yield client


@pytest_asyncio.fixture
async def user1_token(api_client):
    await api_client.post("/api/auth/register", json={
        "email": "user1@test.com", "password": "password123", "full_name": "User One"
    })
    r = await api_client.post("/api/auth/login", data={
        "username": "user1@test.com", "password": "password123"
    })
    return r.json()["access_token"]


@pytest_asyncio.fixture
async def user2_token(api_client):
    await api_client.post("/api/auth/register", json={
        "email": "user2@test.com", "password": "password123", "full_name": "User Two"
    })
    r = await api_client.post("/api/auth/login", data={
        "username": "user2@test.com", "password": "password123"
    })
    return r.json()["access_token"]


@pytest_asyncio.fixture
def auth_headers(user1_token):
    return {"Authorization": f"Bearer {user1_token}"}


@pytest_asyncio.fixture
def auth_headers_user2(user2_token):
    return {"Authorization": f"Bearer {user2_token}"}


@pytest_asyncio.fixture
async def farm_id(api_client, auth_headers):
    r = await api_client.post("/api/farms", json={
        "name": "Test Farm", "location": {"lat": 10.5, "lon": 20.3}
    }, headers=auth_headers)
    return r.json()["id"]


@pytest_asyncio.fixture
async def field_id(api_client, auth_headers, farm_id):
    r = await api_client.post("/api/fields", json={
        "farm_id": farm_id, "name": "Test Field", "crop": "tomato", "growth_stage": "flowering"
    }, headers=auth_headers)
    return r.json()["id"]


@pytest_asyncio.fixture
async def device_uid(api_client, auth_headers, field_id):
    import uuid
    uid = f"esp32-test-{uuid.uuid4().hex[:8]}"
    r = await api_client.post("/api/devices", params={
        "field_id": field_id, "device_uid": uid, "name": "Test Device"
    }, headers=auth_headers)
    # Bring device online via telemetry
    await api_client.post("/api/sensors/telemetry", json={
        "device_id": uid, "timestamp": "2024-01-15T10:00:00Z",
        "soil": {}, "environment": {}, "tank_level": 80, "pump": False
    })
    return uid


@pytest_asyncio.fixture
async def device_id(api_client, auth_headers, field_id):
    import uuid
    uid = f"esp32-test-{uuid.uuid4().hex[:8]}"
    r = await api_client.post("/api/devices", params={
        "field_id": field_id, "device_uid": uid, "name": "Test Device"
    }, headers=auth_headers)
    device_id = r.json()["id"]
    # Bring device online via telemetry
    await api_client.post("/api/sensors/telemetry", json={
        "device_id": uid, "timestamp": "2024-01-15T10:00:00Z",
        "soil": {}, "environment": {}, "tank_level": 80, "pump": False
    })
    return device_id