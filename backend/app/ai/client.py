import httpx
from app.config import settings

class AIService:
    def __init__(self, base_url: str | None = None): self.base_url = base_url or settings.ai_service_url
    async def analyze(self, image_bytes: bytes, filename: str, sensor_data: dict, weather_data: dict, crop_stage: str | None):
        files = {"image": (filename, image_bytes, "application/octet-stream")}
        data = {"sensor_data": __import__("json").dumps(sensor_data), "weather_data": __import__("json").dumps(weather_data), "crop_stage": crop_stage or ""}
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{self.base_url}/ai/analyze", files=files, data=data)
            r.raise_for_status(); return r.json()
