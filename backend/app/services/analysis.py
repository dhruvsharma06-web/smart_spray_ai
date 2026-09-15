from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models import AIAnalysis, DiseaseDetection, PestDetection, ClimateRisk, Decision, Device, SensorReading
from app.ai.client import AIService
from app.decision.client import DecisionService
from app.weather.service import WeatherService
from app.services.storage import ImageStorage
from app.services.alerts import alerts_from_result

class AnalysisOrchestrator:
    def __init__(self):
        self.ai = AIService(); self.decision = DecisionService(); self.weather = WeatherService(); self.storage = ImageStorage()
    async def run(self, db: Session, field, image_bytes: bytes, filename: str):
        weather = await self.weather.get(field.farm.location or {})
        device_ids = list(db.scalars(select(Device.id).where(Device.field_id == field.id)))
        latest = None
        if device_ids:
            latest = db.scalar(select(SensorReading).where(SensorReading.device_id.in_(device_ids)).order_by(SensorReading.device_timestamp.desc()))
        sensor = latest.payload if latest else {}
        result = await self.ai.analyze(image_bytes, filename, sensor, weather, field.growth_stage)
        image_uri = self.storage.save(filename, image_bytes)
        analysis = AIAnalysis(field_id=field.id, image_uri=image_uri, crop=result.get("crop"), diagnosis=result.get("diagnosis") or result.get("disease"), raw_result=result)
        db.add(analysis); db.flush()
        disease = result.get("disease")
        if disease and disease.get("name"):
            db.add(DiseaseDetection(analysis_id=analysis.id, name=disease["name"], confidence=disease.get("confidence", 0), severity=(result.get("severity") or {}).get("level"), affected_area_percent=(result.get("severity") or {}).get("affected_area_percent")))
        for pest in result.get("pests", []):
            db.add(PestDetection(analysis_id=analysis.id, name=pest.get("name", "unknown"), confidence=pest.get("confidence", 0), count=pest.get("count"), detections=pest.get("detections")))
        risk = result.get("climate_risk", {})
        db.add(ClimateRisk(analysis_id=analysis.id, drought=risk.get("drought", 0), heat=risk.get("heat", 0), flood=risk.get("flood", 0), waterlogging=risk.get("waterlogging", 0)))
        decision = await self.decision.decide({"analysis": result, "sensor_data": sensor, "weather_data": weather, "field_id": field.id})
        d = Decision(field_id=field.id, analysis_id=analysis.id, primary_decision=decision["primary_decision"], risk_level=decision.get("risk_level", "UNKNOWN"), result=decision)
        db.add(d); db.flush()
        alerts_from_result(db, field.id, result, decision)
        db.commit()
        return analysis, result, d, decision, weather
