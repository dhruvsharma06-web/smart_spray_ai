from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models import AIAnalysis, DiseaseDetection, PestDetection, ClimateRisk, Decision, Device, SensorReading
from app.ai.client import AIService
from app.decision.client import DecisionService
from app.weather.service import WeatherService
from app.services.storage import ImageStorage
from app.services.alerts import alerts_from_result
from datetime import datetime, timedelta, timezone
from app.config import settings
from pydantic import ValidationError

class AnalysisOrchestrator:
    def __init__(self):
        self.ai = AIService()
        self.decision = DecisionService()
        self.weather = WeatherService()
        self.storage = ImageStorage()
    
    async def run(self, db: Session, field, image_bytes: bytes, filename: str):
        try:
            weather = await self.weather.get(field.farm.location or {})
            device_ids = list(db.scalars(select(Device.id).where(Device.field_id == field.id)))
            latest = None
            if device_ids:
                latest = db.scalar(select(SensorReading).where(SensorReading.device_id.in_(device_ids)).order_by(SensorReading.device_timestamp.desc()))
            sensor = latest.payload if latest else {}
            image_uri = self.storage.save(filename, image_bytes)
            try:
                result = await self.ai.analyze(image_bytes, filename, sensor, weather, field.growth_stage)
            except ValidationError as e:
                raise HTTPException(502, f"AI response validation failed: {e}")
            except ValueError as e:
                raise HTTPException(502, f"AI response validation failed: {e}")
            
            analysis = AIAnalysis(field_id=field.id, image_uri=image_uri, crop=result.get("crop"), diagnosis=result.get("diagnosis") or result.get("disease"), raw_result=result)
            db.add(analysis); db.flush()
            disease = result.get("disease")
            if disease and disease.get("name"):
                dis_conf = disease.get("confidence", 0) if disease.get("confidence") is not None else 0.0
                db.add(DiseaseDetection(
                    analysis_id=analysis.id,
                    name=disease["name"],
                    confidence=dis_conf,
                    severity=(result.get("severity") or {}).get("level") or disease.get("severity"),
                    affected_area_percent=(result.get("severity") or {}).get("affected_area_percent") or disease.get("affected_area_percent")
                ))
            for pest in result.get("pests", []):
                pest_name = pest.get("name") or pest.get("pest_type") or "unknown"
                pest_conf = pest.get("confidence", 0) if pest.get("confidence") is not None else 0.0
                pest_count = pest.get("count")
                pest_detections = pest.get("detections")
                if not pest_detections and pest.get("bounding_box"):
                    pest_detections = {"bounding_box": pest.get("bounding_box")}
                db.add(PestDetection(analysis_id=analysis.id, name=pest_name, confidence=pest_conf, count=pest_count, detections=pest_detections))
            risk = result.get("climate_risk", {})
            db.add(ClimateRisk(analysis_id=analysis.id, drought=risk.get("drought", 0), heat=risk.get("heat", 0), flood=risk.get("flood", 0), waterlogging=risk.get("waterlogging", 0)))
            try:
                decision = await self.decision.decide({"analysis": result, "sensor_data": sensor, "weather_data": weather, "field_id": field.id})
            except (ValidationError, ValueError) as e:
                raise HTTPException(502, f"Decision Engine response validation failed: {e}")
            created_at = datetime.now(timezone.utc)
            expires_at = created_at + timedelta(seconds=settings.decision_ttl_seconds)
            d = Decision(
                field_id=field.id,
                analysis_id=analysis.id,
                primary_decision=decision["primary_decision"],
                risk_level=decision.get("risk_level", "UNKNOWN"),
                result=decision,
                created_at=created_at,
                expires_at=expires_at,
            )
            db.add(d); db.flush()
            alerts_from_result(db, field.id, result, decision)
            db.commit()
            decision_payload = {"decision_id": d.id, **decision}
            return analysis, result, d, decision_payload, weather
        finally:
            await self.ai.close()
            await self.decision.close()
