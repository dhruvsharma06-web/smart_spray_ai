"""
Pydantic schemas for Severity Assessment.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field

SeverityLevel = Literal["healthy", "low", "moderate", "high", "critical"]


class SeverityAssessmentResult(BaseModel):
    """Damage and infection severity assessment."""

    level: SeverityLevel = Field(..., description="Categorical severity level.")
    affected_area_percent: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Estimated percentage of foliage or plant canopy exhibiting symptoms.",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    progression_risk: Literal["low", "medium", "rapid"] = "medium"
