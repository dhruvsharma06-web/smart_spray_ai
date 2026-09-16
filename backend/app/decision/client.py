import httpx
import logging
from pydantic import ValidationError
from app.config import settings
from app.services.resilient_client import create_decision_client
from app.schemas.decision_response import DecisionResponseOut

logger = logging.getLogger(__name__)

class DecisionService:
    def __init__(self, base_url: str | None = None): 
        self.base_url = base_url or settings.decision_service_url
        self._client = create_decision_client(self.base_url)
    
    async def decide(self, payload: dict) -> dict:
        try:
            r = await self._client.post("/decision", json=payload)
            r.raise_for_status()
            data = r.json()
            validated = DecisionResponseOut.model_validate(data)
            return validated.model_dump(mode="json")
        except ValidationError as e:
            logger.error(f"Decision response validation failed: {e}")
            raise
        except httpx.TimeoutException:
            logger.error("Decision service timeout after retries")
            raise
        except httpx.ConnectError:
            logger.error("Decision service connection failed after retries")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"Decision service returned error: {e.response.status_code}")
            raise
    
    async def health(self) -> dict:
        try:
            r = await self._client.get("/health")
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"Decision service health check failed: {e}")
            raise

    async def close(self):
        await self._client.close()
