import httpx
from app.config import settings
class DecisionService:
    def __init__(self, base_url: str | None = None): self.base_url = base_url or settings.decision_service_url
    async def decide(self, payload: dict):
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(f"{self.base_url}/decision", json=payload)
            r.raise_for_status(); return r.json()
