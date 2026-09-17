import httpx
import logging
from app.config import settings
from app.services.resilient_client import create_ai_client
from app.schemas.ai_response import AnalysisResult, validate_ai_response
from pydantic import ValidationError

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self, base_url: str | None = None): 
        self.base_url = base_url or settings.ai_service_url
        self._client = create_ai_client(self.base_url)
    
    async def analyze(self, image_bytes: bytes, filename: str, sensor_data: dict, weather_data: dict, crop_stage: str | None):
        files = {"image": (filename, image_bytes, "application/octet-stream")}
        import json
        data = {"sensor_data": json.dumps(sensor_data), "weather_data": json.dumps(weather_data), "crop_stage": crop_stage or ""}
        try:
            r = await self._client.post("/ai/analyze", files=files, data=data)
            r.raise_for_status()
            raw_response = r.json()
            
            # Validate AI response against strict schema
            try:
                validated = validate_ai_response(raw_response)
                logger.debug("AI response validation passed")
                return validated.model_dump()
            except ValidationError as e:
                logger.error(f"AI response validation failed: {e}")
                raise ValueError(f"AI response validation failed: {e}")
                
        except httpx.TimeoutException:
            logger.error("AI service timeout after retries")
            raise
        except httpx.ConnectError:
            logger.error("AI service connection failed after retries")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"AI service returned error: {e.response.status_code}")
            raise
    
    async def close(self):
        await self._client.close()
