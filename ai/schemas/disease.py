"""
Pydantic schemas for Crop Disease Detection.
Supports both image-level classification and localized bounding-box detections.
"""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, model_validator
from ..config.settings import get_settings


class BoundingBox(BaseModel):
    """
    Normalized bounding box coordinates.
    Can be represented as coordinates or converted to [ymin, xmin, ymax, xmax].
    """

    ymin: float = Field(..., ge=0.0, le=1.0, description="Top coordinate normalized [0-1].")
    xmin: float = Field(..., ge=0.0, le=1.0, description="Left coordinate normalized [0-1].")
    ymax: float = Field(..., ge=0.0, le=1.0, description="Bottom coordinate normalized [0-1].")
    xmax: float = Field(..., ge=0.0, le=1.0, description="Right coordinate normalized [0-1].")

    def to_xyxy(self) -> List[float]:
        """Return [xmin, ymin, xmax, ymax] list."""
        return [self.xmin, self.ymin, self.xmax, self.ymax]

    def to_list(self) -> List[float]:
        """Return [ymin, xmin, ymax, xmax] list."""
        return [self.ymin, self.xmin, self.ymax, self.xmax]


class DiseaseDetectionBox(BaseModel):
    """Single localized disease lesion or affected spot."""

    label: str = Field(..., description="Detected symptom or disease name.")
    confidence: float = Field(..., ge=0.0, le=1.0)
    bbox: Union[BoundingBox, List[float]] = Field(
        ...,
        description="Bounding box as BoundingBox object or [ymin, xmin, ymax, xmax] list.",
    )


class DiseaseDetectionResult(BaseModel):
    """
    Structured output contract for disease detection and diagnosis.
    Provides crop-aware diagnosis with confidence governance and optional localization.
    """

    disease: str = Field(
        ...,
        description="Standard disease identifier (e.g. 'early_blight', 'late_blight', 'healthy').",
    )
    display_name: str = Field(
        default="",
        description="Human readable formatted disease name (e.g. 'Early Blight').",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Probability or model confidence score between 0.0 and 1.0.",
    )
    crop: Optional[str] = Field(
        default=None,
        description="Target crop context (e.g. 'tomato', 'potato').",
    )
    is_healthy: bool = Field(
        default=False,
        description="True if the foliage appears healthy without disease lesions.",
    )
    confidence_level: Literal["high", "moderate", "low"] = Field(
        default="high",
        description="Categorical confidence rating based on AISettings thresholds.",
    )
    requires_confirmation: bool = Field(
        default=False,
        description="True if low confidence or diagnostic ambiguity warrants expert confirmation.",
    )
    detections: List[DiseaseDetectionBox] = Field(
        default_factory=list,
        description="Localized bounding boxes for detected disease lesions.",
    )
    affected_area_percent: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Estimated percentage of visible leaf area affected by disease lesions.",
    )
    symptoms: List[str] = Field(
        default_factory=list,
        description="Identified botanical symptoms (e.g. 'concentric_rings', 'dark_spots').",
    )

    # Backwards compatibility property so `result.name` works seamlessly
    @property
    def name(self) -> str:
        """Alias for disease identifier."""
        return self.disease

    @model_validator(mode="before")
    @classmethod
    def handle_legacy_name_field(cls, data: Any) -> Any:
        """Support 'name' field if passed instead of 'disease' for backward compatibility."""
        if isinstance(data, dict):
            if "name" in data and "disease" not in data:
                data["disease"] = data["name"]
            if not data.get("display_name") and "disease" in data:
                data["display_name"] = str(data["disease"]).replace("_", " ").title()
            # If disease is healthy, ensure is_healthy flag is aligned
            if data.get("disease") == "healthy":
                data["is_healthy"] = True
        return data

    @model_validator(mode="after")
    def sync_confidence_and_confirmation(self) -> "DiseaseDetectionResult":
        """Enforce system confidence governance rules."""
        settings = get_settings()
        self.confidence_level = settings.get_confidence_level(self.confidence)
        if settings.is_confirmation_required(self.confidence) or self.confidence < 0.60:
            self.requires_confirmation = True
        if not self.display_name:
            self.display_name = self.disease.replace("_", " ").title()
        return self
