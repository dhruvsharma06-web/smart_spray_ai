"""
Pydantic schemas for Plant and Crop Identification.
Defines contracts for open-world multimodal crop classification results.
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

ConfidenceTier = Literal["high", "moderate", "low"]
PlantPart = Literal["leaves", "stem", "fruit", "flower", "roots", "whole_plant", "unknown"]
CropGrowthStage = Literal[
    "seedling", "vegetative", "flowering", "fruiting", "maturation", "unknown"
]


class AlternativeCropCandidate(BaseModel):
    """Potential alternative identification candidate when ambiguity exists."""

    crop_name: str
    confidence: float = Field(ge=0.0, le=1.0)


class CropIdentificationResult(BaseModel):
    """
    Structured output contract for plant and crop identification.
    Handles open-world identification via multimodal GenAI or specialized classifiers.
    """

    crop_name: str = Field(
        ...,
        description="Identified common crop/plant name in lowercase (e.g. 'tomato', 'maize', 'potato').",
    )
    scientific_name: Optional[str] = Field(
        None,
        description="Botanical binomial nomenclature (e.g. 'Solanum lycopersicum').",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Probability or model confidence score between 0.0 and 1.0.",
    )
    confidence_level: ConfidenceTier = Field(
        ...,
        description="Categorical confidence rating ('high' >= 0.85, 'moderate' 0.60-0.85, 'low' < 0.60).",
    )
    requires_confirmation: bool = Field(
        ...,
        description="Flag indicating if low confidence or ambiguity requires farmer/expert confirmation.",
    )
    detected_parts: List[PlantPart] = Field(
        default_factory=list,
        description="Visible anatomical parts of the plant in the image.",
    )
    growth_stage_visual: CropGrowthStage = Field(
        default="unknown",
        description="Visually estimated growth stage.",
    )
    is_plant: bool = Field(
        default=True,
        description="Whether a valid plant/crop was detected in the image.",
    )
    reasoning: str = Field(
        default="",
        description="Botanical and visual reasoning explaining why this crop was identified.",
    )
    alternative_candidates: List[AlternativeCropCandidate] = Field(
        default_factory=list,
        description="Other close candidate classifications if confidence is not definitive.",
    )

    @field_validator("crop_name", mode="before")
    @classmethod
    def normalize_crop_name(cls, v: str) -> str:
        """Normalize crop name to lower-case stripped string."""
        if isinstance(v, str):
            return v.strip().lower()
        return v
