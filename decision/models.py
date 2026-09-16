from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PrimaryDecision(str, Enum):
    SPRAY = "SPRAY"
    IRRIGATE = "IRRIGATE"
    DELAY_SPRAY = "DELAY_SPRAY"
    MONITOR = "MONITOR"
    WARN = "WARN"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ActionType(str, Enum):
    SPRAY = "SPRAY"
    IRRIGATION = "IRRIGATION"
    IRRIGATE = "IRRIGATE"
    DELAY_SPRAY = "DELAY_SPRAY"
    MONITOR = "MONITOR"
    WARN = "WARN"


class Priority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DecisionAction(BaseModel):
    type: ActionType
    priority: Priority = Priority.MEDIUM


class DecisionRequest(BaseModel):
    analysis: Dict[str, Any] = Field(default_factory=dict, description="AI analysis result payload")
    sensor_data: Dict[str, Any] = Field(default_factory=dict, description="IoT sensor telemetry")
    weather_data: Dict[str, Any] = Field(default_factory=dict, description="Weather forecast and current conditions")
    field_id: Optional[int] = Field(default=None, description="Optional target field identifier")

    model_config = {"extra": "allow"}


class DecisionResponse(BaseModel):
    primary_decision: PrimaryDecision
    risk_level: RiskLevel
    actions: List[DecisionAction] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    requires_confirmation: bool = False

    model_config = {"extra": "allow"}
