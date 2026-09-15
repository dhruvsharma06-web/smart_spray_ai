"""
Pydantic schemas for Pest Detection and Object Localization.
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, model_validator
from .disease import BoundingBox
from ..config.settings import get_settings


class DetectedPest(BaseModel):
    """Single detected pest instance with bounding box and classification."""

    pest_type: str = Field(..., description="Pest identifier (e.g. 'aphid', 'whitefly', 'caterpillar', 'beetle').")
    confidence: float = Field(..., ge=0.0, le=1.0)
    bounding_box: BoundingBox


class PestDetectionResult(BaseModel):
    """Aggregate result from pest detection model."""

    pests: List[DetectedPest] = Field(default_factory=list)
    total_count: int = Field(default=0, ge=0)
    dominant_pest: Optional[str] = None
    infestation_severity: Literal["none", "low", "moderate", "high", "severe"] = "none"
    confidence: float = Field(default=0.90, ge=0.0, le=1.0)
    confidence_level: Literal["high", "moderate", "low"] = "high"
    requires_confirmation: bool = False

    @model_validator(mode="after")
    def sync_confidence_and_counts(self) -> "PestDetectionResult":
        """Enforce count consistency and confidence governance."""
        settings = get_settings()
        self.total_count = len(self.pests)
        if self.pests and not self.dominant_pest:
            # Find most frequent pest
            counts = {}
            for p in self.pests:
                counts[p.pest_type] = counts.get(p.pest_type, 0) + 1
            self.dominant_pest = max(counts, key=counts.get)
            top_conf = max(p.confidence for p in self.pests)
            self.confidence = top_conf
        elif not self.pests:
            self.infestation_severity = "none"

        # Determine infestation severity based on count
        if self.total_count == 0:
            self.infestation_severity = "none"
        elif self.total_count <= 2:
            self.infestation_severity = "low"
        elif self.total_count <= 5:
            self.infestation_severity = "moderate"
        elif self.total_count <= 10:
            self.infestation_severity = "high"
        else:
            self.infestation_severity = "severe"

        self.confidence_level = settings.get_confidence_level(self.confidence)
        if settings.is_confirmation_required(self.confidence) or self.confidence < 0.60:
            self.requires_confirmation = True

        return self
