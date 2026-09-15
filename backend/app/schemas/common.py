from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from typing import Any

class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class ErrorResponse(BaseModel):
    detail: str

class CropOut(BaseModel):
    name: str
    confidence: float = Field(ge=0, le=1)

class DiagnosisOut(BaseModel):
    type: str | None = None
    name: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    severity: str | None = None
    affected_area_percent: float | None = Field(default=None, ge=0, le=100)

class ClimateRiskOut(BaseModel):
    drought: float = Field(ge=0, le=1)
    heat: float = Field(ge=0, le=1)
    flood: float = Field(ge=0, le=1)
    waterlogging: float = Field(ge=0, le=1)

class AnalysisResult(BaseModel):
    crop: CropOut
    disease: dict | None = None
    pests: list[dict] = []
    nutrient_deficiency: dict | None = None
    severity: dict | None = None
    climate_risk: ClimateRiskOut
    requires_confirmation: bool = False

class DecisionResult(BaseModel):
    primary_decision: str
    risk_level: str
    actions: list[dict] = []
    warnings: list[str] = []
    requires_confirmation: bool = False

class TelemetryIn(BaseModel):
    device_id: str
    timestamp: datetime
    soil: dict[str, Any] = {}
    environment: dict[str, Any] = {}
    tank_level: float | None = Field(default=None, ge=0, le=100)
    pump: bool = False

class TelemetryOut(BaseModel):
    reading_id: int
    device_id: str
    device_timestamp: datetime
    server_timestamp: datetime
    accepted: bool = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=8)
    full_name: str

class UserOut(ORMModel):
    id: int
    email: str
    full_name: str
    is_active: bool

class FarmCreate(BaseModel):
    name: str
    location: dict | None = None

class FarmOut(ORMModel):
    id: int
    name: str
    location: dict | None

class FieldCreate(BaseModel):
    farm_id: int
    name: str
    area_hectares: float | None = Field(default=None, gt=0)
    crop: str | None = None
    growth_stage: str | None = None

class FieldOut(ORMModel):
    id: int
    farm_id: int
    name: str
    area_hectares: float | None
    crop: str | None
    growth_stage: str | None

class AlertOut(ORMModel):
    id: int
    field_id: int
    alert_type: str
    severity: str
    message: str
    acknowledged: bool
    created_at: datetime
