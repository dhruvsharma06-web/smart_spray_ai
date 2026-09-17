"""
Pydantic schemas for Person 3 Decision Engine.
Defines strict, typed contracts for action recommendations, safety statuses, and decision audits.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    """Supported operational actions decided by the Decision Engine."""

    SPRAY = "SPRAY"
    IRRIGATE = "IRRIGATE"
    WARN = "WARN"
    DELAY = "DELAY"
    NO_ACTION = "NO_ACTION"


class PriorityLevel(str, Enum):
    """Urgency and severity classification for decisions."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SafetyStatus(str, Enum):
    """Safety state assessment result."""

    FIELD_HEALTHY = "FIELD_HEALTHY"
    SAFE_TO_SPRAY = "SAFE_TO_SPRAY"
    SAFE_TO_IRRIGATE = "SAFE_TO_IRRIGATE"
    WEATHER_DELAY = "WEATHER_DELAY"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    NO_VERIFIED_TREATMENT = "NO_VERIFIED_TREATMENT"
    CLIMATE_HAZARD = "CLIMATE_HAZARD"
    SAFETY_BLOCK = "SAFETY_BLOCK"
    TELEMETRY_INVALID = "TELEMETRY_INVALID"
    TELEMETRY_MISSING = "TELEMETRY_MISSING"


class DecisionAudit(BaseModel):
    """Traceable audit record for debugging and SIH evaluation."""

    triggered_rules: List[str] = Field(default_factory=list, description="List of rule IDs triggered during evaluation.")
    inputs_considered: Dict[str, Any] = Field(default_factory=dict, description="Summary of inputs evaluated.")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 timestamp when decision was computed.",
    )


class DecisionResult(BaseModel):
    """
    Standard output contract for Person 3 Decision Engine.
    Exposes deterministic action recommendations for Person 2/4 execution.
    """

    action: ActionType = Field(..., description="Recommended operational action.")
    reason: str = Field(..., description="Human-readable explanation of why this action was selected.")
    priority: PriorityLevel = Field(..., description="Urgency priority rating.")
    requires_confirmation: bool = Field(
        ..., description="True if farmer/operator confirmation is required before taking action."
    )
    safety_status: SafetyStatus = Field(..., description="Categorical safety status code.")
    duration_minutes: Optional[float] = Field(
        default=None, description="Recommended operational duration in minutes (if applicable)."
    )
    verified_treatment: Optional[Dict[str, Any]] = Field(
        default=None, description="Verified treatment details from RAG knowledge base (for SPRAY/DELAY actions)."
    )
    audit: DecisionAudit = Field(..., description="Traceable audit log for rules and inputs.")
