import httpx
from app.config import settings
class GenAIService:
    async def explain(self, analysis: dict, decision: dict):
        payload = {"analysis": analysis, "decision": decision}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(f"{settings.genai_service_url}/assistant/explain", json=payload)
                r.raise_for_status(); return r.json()
        except Exception:
            crop = analysis.get("crop", {}).get("name", "the crop")
            disease = analysis.get("disease") or {}
            name = disease.get("name")
            decision_name = decision.get("primary_decision", "MONITOR")
            text = f"The system identified {crop}."
            if name: text += f" Possible {name} was detected."
            text += f" Recommended action: {decision_name.replace('_', ' ').lower()}."
            return {"text": text, "source": "fallback"}
