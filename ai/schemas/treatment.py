"""
Pydantic schemas for Verified Agricultural Treatments.
Guarantees strict compliance with verified agricultural databases; no hallucinated chemicals.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class VerifiedTreatmentRecord(BaseModel):
    """
    Certified agricultural treatment entry from authoritative database.
    Fields enforce non-hallucinatory pesticide and management specifications.
    """

    crop: str = Field(..., description="Target crop.")
    target_pest_or_disease: str = Field(..., description="Specific pathogen or pest approved for.")
    product: str = Field(..., description="Commercial/registered product name.")
    active_ingredient: str = Field(..., description="Chemical or biological active constituent.")
    formulation: str = Field(..., description="Formulation code (e.g. WP, SC, EC, GR).")
    application_method: str = Field(..., description="Foliar spray, soil drench, root dip, etc.")
    approved_crop: str = Field(..., description="Regulatory approved crop.")
    approved_target: str = Field(..., description="Regulatory approved target organism.")
    label_rate: str = Field(..., description="Official label dilution or dosage (e.g. '2.5 ml/L of water').")
    pre_harvest_interval_days: int = Field(..., ge=0, description="Minimum days between application and harvest (PHI).")
    reentry_interval_hours: Optional[int] = Field(default=24, ge=0, description="REI in hours.")
    safety_information: str = Field(..., description="Mandatory PPE, handling precautions, pollinator warnings.")
    source: str = Field(..., description="Regulatory registry or university extension authority.")
    verification_date: str = Field(..., description="ISO date of verification in catalog.")
    is_organic_certified: bool = Field(default=False)
    contraindications: List[str] = Field(default_factory=list)
