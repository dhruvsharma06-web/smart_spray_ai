"""
Pydantic schemas for Nutrient Deficiency Assessment.
Distinguishes between visual symptom indicators and lab-confirmed deficiencies.
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, model_validator
from ..config.settings import get_settings

NutrientElement = Literal["nitrogen", "phosphorus", "potassium", "iron", "magnesium", "zinc"]


class NutrientDeficiencyItem(BaseModel):
    """Specific nutrient deficiency observation."""

    nutrient: NutrientElement
    confidence: float = Field(..., ge=0.0, le=1.0)
    is_visual_indicator_only: bool = Field(
        default=True,
        description="Always true for image-based inference; distinguishes visual symptom from lab-confirmed deficiency.",
    )
    symptom_description: str = Field(..., description="Observed symptom like chlorosis, necrosis, purpling.")
    affected_leaf_zone: Literal["older_leaves", "younger_leaves", "all_leaves", "interveinal", "margins"] = "all_leaves"


class NutrientDeficiencyResult(BaseModel):
    """Aggregate nutrient deficiency assessment."""

    has_deficiency: bool = False
    suspected_deficiencies: List[NutrientDeficiencyItem] = Field(default_factory=list)
    primary_deficiency: Optional[NutrientElement] = None
    confidence: float = Field(default=0.90, ge=0.0, le=1.0)
    confidence_level: Literal["high", "moderate", "low"] = "high"
    requires_confirmation: bool = False
    note: str = Field(
        default="Visual inspection suggests possible deficiencies. Soil/tissue testing is required for confirmation."
    )

    @model_validator(mode="after")
    def sync_confidence_and_governance(self) -> "NutrientDeficiencyResult":
        """Enforce confidence governance rules."""
        settings = get_settings()
        if self.suspected_deficiencies:
            self.has_deficiency = True
            if not self.primary_deficiency:
                top_item = max(self.suspected_deficiencies, key=lambda x: x.confidence)
                self.primary_deficiency = top_item.nutrient
                self.confidence = top_item.confidence
        else:
            self.has_deficiency = False
            self.primary_deficiency = None

        self.confidence_level = settings.get_confidence_level(self.confidence)
        if settings.is_confirmation_required(self.confidence) or self.confidence < 0.60:
            self.requires_confirmation = True
        return self
