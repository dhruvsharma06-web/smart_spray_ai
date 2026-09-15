import pytest
from httpx import ASGITransport, AsyncClient
from mock_decision.main import app
@pytest.mark.asyncio
async def test_mock_decision_spray():
    async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as c:
        r=await c.post('/decision',json={'analysis':{'climate_risk':{'drought':.2}},'weather_data':{'rain_probability':10}})
    assert r.status_code==200
    assert r.json()['primary_decision']=='SPRAY'
