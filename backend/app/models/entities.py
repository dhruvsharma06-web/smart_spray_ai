from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.session import Base

def now(): return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    farms = relationship("Farm", back_populates="owner", cascade="all, delete-orphan")

class Farm(Base):
    __tablename__ = "farms"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    location: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    owner = relationship("User", back_populates="farms")
    fields = relationship("Field", back_populates="farm", cascade="all, delete-orphan")

class Field(Base):
    __tablename__ = "fields"
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    area_hectares: Mapped[float | None] = mapped_column(Float)
    crop: Mapped[str | None] = mapped_column(String(100))
    growth_stage: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    farm = relationship("Farm", back_populates="fields")
    devices = relationship("Device", back_populates="field", cascade="all, delete-orphan")

class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    device_uid: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    device_type: Mapped[str] = mapped_column(String(50), default="ESP32")
    status: Mapped[str] = mapped_column(String(30), default="OFFLINE")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_command_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tank_level: Mapped[float | None] = mapped_column(Float)
    pump_active: Mapped[bool] = mapped_column(Boolean, default=False)
    field = relationship("Field", back_populates="devices")

class SensorReading(Base):
    __tablename__ = "sensor_readings"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    device_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    server_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    payload: Mapped[dict] = mapped_column(JSON)

class CropRecord(Base):
    __tablename__ = "crop_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    crop: Mapped[str] = mapped_column(String(100))
    growth_stage: Mapped[str | None] = mapped_column(String(100))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class AIAnalysis(Base):
    __tablename__ = "ai_analyses"
    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id"), index=True)
    image_uri: Mapped[str | None] = mapped_column(String(1000))
    crop: Mapped[dict | None] = mapped_column(JSON)
    diagnosis: Mapped[dict | None] = mapped_column(JSON)
    raw_result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class DiseaseDetection(Base):
    __tablename__ = "disease_detections"
    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("ai_analyses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    confidence: Mapped[float] = mapped_column(Float)
    severity: Mapped[str | None] = mapped_column(String(30))
    affected_area_percent: Mapped[float | None] = mapped_column(Float)

class PestDetection(Base):
    __tablename__ = "pest_detections"
    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("ai_analyses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    confidence: Mapped[float] = mapped_column(Float)
    count: Mapped[int | None] = mapped_column(Integer)
    detections: Mapped[dict | None] = mapped_column(JSON)

class ClimateRisk(Base):
    __tablename__ = "climate_risk"
    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("ai_analyses.id", ondelete="CASCADE"), index=True)
    drought: Mapped[float] = mapped_column(Float, default=0)
    heat: Mapped[float] = mapped_column(Float, default=0)
    flood: Mapped[float] = mapped_column(Float, default=0)
    waterlogging: Mapped[float] = mapped_column(Float, default=0)

class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id"), index=True)
    analysis_id: Mapped[int | None] = mapped_column(ForeignKey("ai_analyses.id"), nullable=True)
    primary_decision: Mapped[str] = mapped_column(String(50))
    risk_level: Mapped[str] = mapped_column(String(30))
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class SprayEvent(Base):
    __tablename__ = "spray_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    decision_id: Mapped[int | None] = mapped_column(ForeignKey("decisions.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True, index=True, nullable=True)

class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    alert_type: Mapped[str] = mapped_column(String(60), index=True)
    severity: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(Text)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)

class Treatment(Base):
    __tablename__ = "treatments"
    id: Mapped[int] = mapped_column(primary_key=True)
    crop: Mapped[str] = mapped_column(String(100), index=True)
    target: Mapped[str] = mapped_column(String(150), index=True)
    product: Mapped[str] = mapped_column(String(255))
    active_ingredient: Mapped[str] = mapped_column(String(255))
    formulation: Mapped[str | None] = mapped_column(String(100))
    application_method: Mapped[str | None] = mapped_column(String(100))
    approved_crop: Mapped[str] = mapped_column(String(100))
    approved_target: Mapped[str] = mapped_column(String(150))
    label_rate: Mapped[str | None] = mapped_column(String(255))
    pre_harvest_interval: Mapped[str | None] = mapped_column(String(100))
    safety: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(1000))
    verification_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    analysis_id: Mapped[int | None] = mapped_column(ForeignKey("ai_analyses.id"), nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(100))
    entity_id: Mapped[str | None] = mapped_column(String(100))
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
