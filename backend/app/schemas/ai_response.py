# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Any, Optional, Union


class BoundingBox(BaseModel):
    ymin: float = Field(ge=0.0, le=1.0)
    xmin: float = Field(ge=0.0, le=1.0)
    ymax: float = Field(ge=0.0, le=1.0)
    xmax: float = Field(ge=0.0, le=1.0)


class CropOut(BaseModel):
    name: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    scientific_name: Optional[str] = None
    confidence_level: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def handle_crop_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "crop_name" in data and "name" not in data:
                data["name"] = data["crop_name"]
        return data


class DiseaseDetectionBox(BaseModel):
    label: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    bbox: Optional[Union[BoundingBox, list[float]]] = None


class DiseaseOut(BaseModel):
    name: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    severity: Optional[str] = None
    affected_area_percent: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    display_name: Optional[str] = None
    is_healthy: Optional[bool] = None
    symptoms: Optional[list[str]] = None
    detections: Optional[list[Union[DiseaseDetectionBox, dict[str, Any]]]] = None

    @model_validator(mode="before")
    @classmethod
    def handle_disease_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "disease" in data and "name" not in data:
                data["name"] = data["disease"]
        return data

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v.strip()) == 0:
            return None
        return v


class PestOut(BaseModel):
    name: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    count: Optional[int] = None
    bounding_box: Optional[BoundingBox] = None
    detections: Optional[Union[dict[str, Any], list[Any]]] = None

    @model_validator(mode="before")
    @classmethod
    def handle_pest_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "pest_type" in data and "name" not in data:
                data["name"] = data["pest_type"]
        return data


class SeverityOut(BaseModel):
    level: Optional[str] = None
    affected_area_percent: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    progression_risk: Optional[str] = None


class ClimateRiskOut(BaseModel):
    drought: float = Field(ge=0.0, le=1.0)
    heat: float = Field(ge=0.0, le=1.0)
    flood: float = Field(ge=0.0, le=1.0)
    waterlogging: float = Field(ge=0.0, le=1.0)


class AnalysisResult(BaseModel):
    crop: CropOut
    disease: Optional[DiseaseOut] = None
    pests: list[PestOut] = []
    nutrient_deficiency: Optional[Union[str, dict[str, Any]]] = None
    severity: Optional[SeverityOut] = None
    climate_risk: ClimateRiskOut
    requires_confirmation: bool = False
    recommendations: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None

    model_config = {"extra": "allow"}


def validate_ai_response(raw: dict) -> AnalysisResult:
    """
    Validate AI response against strict schema.
    Raises ValidationError if response is malformed.
    """
    return AnalysisResult.model_validate(raw)