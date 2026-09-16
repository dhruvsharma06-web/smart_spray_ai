from enum import Enum
from typing import List, Optional
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


class DecisionActionOut(BaseModel):
    type: ActionType
    priority: Priority = Priority.MEDIUM


class DecisionResponseOut(BaseModel):
    primary_decision: PrimaryDecision
    risk_level: RiskLevel
    actions: List[DecisionActionOut] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    requires_confirmation: bool = False

    model_config = {"extra": "allow"}
