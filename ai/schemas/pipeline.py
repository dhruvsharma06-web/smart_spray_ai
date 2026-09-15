"""
Pydantic schemas for the Unified analyze_field() Pipeline.
Enforces the exact JSON schema contract consumed by Person 2's Decision Engine.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from .climate import ClimateRiskResult, SensorTelemetry
from .crop import CropIdentificationResult
from .disease import DiseaseDetectionResult
from .nutrient import NutrientDeficiencyResult
from .pest import DetectedPest
from .severity import SeverityAssessmentResult


class CropSummary(BaseModel):
    """Summary crop block consumed by Decision Engine."""

    name: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class DiseaseSummary(BaseModel):
    """Summary disease block consumed by Decision Engine."""

    name: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class SeveritySummary(BaseModel):
    """Summary severity block consumed by Decision Engine."""

    level: str
    affected_area_percent: Optional[float] = None


class ClimateRiskSummary(BaseModel):
    """Climate risk vector consumed by Decision Engine."""

    drought: float = Field(..., ge=0.0, le=1.0)
    heat: float = Field(..., ge=0.0, le=1.0)
    flood: float = Field(..., ge=0.0, le=1.0)
    waterlogging: float = Field(..., ge=0.0, le=1.0)


class FieldAnalysisOutput(BaseModel):
    """
    Standard output contract of the AI module for Person 2's Decision Engine.
    Matches exact JSON structure specified in architecture requirements.
    """

    crop: CropSummary
    disease: Optional[DiseaseSummary] = None
    pests: List[DetectedPest] = Field(default_factory=list)
    nutrient_deficiency: Optional[str] = None
    severity: Optional[SeveritySummary] = None
    climate_risk: ClimateRiskSummary
    requires_confirmation: bool = Field(
        ...,
        description="True if any model confidence < 0.60 or significant diagnostic ambiguity exists.",
    )

    # Optional metadata dictionary for debugging/GenAI without breaking contract
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Internal telemetry, detailed reasoning, or GenAI explanation reference.",
    )


class FieldAnalysisInput(BaseModel):
    """Input payload container for the unified pipeline."""

    crop_stage: str = "vegetative"
    sensor_data: Optional[Dict[str, Any]] = None
    weather_data: Optional[Dict[str, Any]] = None
