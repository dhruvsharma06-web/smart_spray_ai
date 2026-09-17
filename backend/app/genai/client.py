import httpx
import logging
from app.config import settings
from app.services.resilient_client import create_genai_client

logger = logging.getLogger(__name__)

class GenAIService:
    def __init__(self):
        self._client = create_genai_client(settings.genai_service_url)
    
    async def explain(self, analysis: dict, decision: dict):
        payload = {"analysis": analysis, "decision": decision}
        try:
            r = await self._client.post("/assistant/explain", json=payload)
            r.raise_for_status()
            return r.json()
        except httpx.TimeoutException:
            logger.warning("GenAI service timeout after retries, using fallback")
            return self._fallback(analysis, decision)
        except httpx.ConnectError:
            logger.warning("GenAI service connection failed after retries, using fallback")
            return self._fallback(analysis, decision)
        except httpx.HTTPStatusError as e:
            logger.warning(f"GenAI service returned error: {e.response.status_code}, using fallback")
            return self._fallback(analysis, decision)
        except Exception as e:
            logger.warning(f"GenAI service unexpected error: {e}, using fallback")
            return self._fallback(analysis, decision)
    
    def _fallback(self, analysis: dict, decision: dict) -> dict:
        crop = analysis.get("crop", {}).get("name", "the crop")
        disease = analysis.get("disease") or {}
        name = disease.get("name")
        decision_name = decision.get("primary_decision", "MONITOR")
        text = f"The system identified {crop}."
        if name: text += f" Possible {name} was detected."
        text += f" Recommended action: {decision_name.replace('_', ' ').lower()}."
        return {"text": text, "source": "fallback"}
    
    async def close(self):
        await self._client.close()
