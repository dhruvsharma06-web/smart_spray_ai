"""
Decision Engine Configuration settings and thresholds.
Allows customizing operational parameters without altering core decision rules.
"""

from functools import lru_cache
import os
from pydantic import BaseModel, Field
from ..config.settings import get_settings


class DecisionSettings(BaseModel):
    """Configuration parameters and threshold boundaries for Decision Engine."""

    # Confidence Thresholds (aligned with AISettings)
    HIGH_CONFIDENCE_THRESHOLD: float = Field(default=0.85, ge=0.0, le=1.0)
    LOW_CONFIDENCE_THRESHOLD: float = Field(default=0.60, ge=0.0, le=1.0)

    # Soil Moisture Boundaries (%)
    SOIL_MOISTURE_IRRIGATE_THRESHOLD: float = Field(default=25.0, ge=0.0, le=100.0)
    SOIL_MOISTURE_SATURATED_THRESHOLD: float = Field(default=80.0, ge=0.0, le=100.0)

    # Climate & Weather Blockers
    PRECIPITATION_SPRAY_BLOCK_THRESHOLD: float = Field(default=15.0, ge=0.0)  # mm/24h rain
    FLOOD_RISK_BLOCK_THRESHOLD: float = Field(default=0.50, ge=0.0, le=1.0)
    WATERLOGGING_RISK_BLOCK_THRESHOLD: float = Field(default=0.50, ge=0.0, le=1.0)
    DROUGHT_RISK_IRRIGATE_THRESHOLD: float = Field(default=0.50, ge=0.0, le=1.0)
    CRITICAL_CLIMATE_HAZARD_THRESHOLD: float = Field(default=0.80, ge=0.0, le=1.0)

    # Operational Defaults
    DEFAULT_IRRIGATION_DURATION_MINUTES: float = Field(default=30.0, ge=0.0)

    @classmethod
    def load_from_env(cls) -> "DecisionSettings":
        """Load settings with environment variable overrides if present."""
        ai_settings = get_settings()
        return cls(
            HIGH_CONFIDENCE_THRESHOLD=ai_settings.HIGH_CONFIDENCE_THRESHOLD,
            LOW_CONFIDENCE_THRESHOLD=ai_settings.LOW_CONFIDENCE_THRESHOLD,
            SOIL_MOISTURE_IRRIGATE_THRESHOLD=float(
                os.getenv("SOIL_MOISTURE_IRRIGATE_THRESHOLD", 25.0)
            ),
            SOIL_MOISTURE_SATURATED_THRESHOLD=float(
                os.getenv("SOIL_MOISTURE_SATURATED_THRESHOLD", 80.0)
            ),
            PRECIPITATION_SPRAY_BLOCK_THRESHOLD=float(
                os.getenv("PRECIPITATION_SPRAY_BLOCK_THRESHOLD", 15.0)
            ),
            FLOOD_RISK_BLOCK_THRESHOLD=float(
                os.getenv("FLOOD_RISK_BLOCK_THRESHOLD", 0.50)
            ),
            WATERLOGGING_RISK_BLOCK_THRESHOLD=float(
                os.getenv("WATERLOGGING_RISK_BLOCK_THRESHOLD", 0.50)
            ),
            DROUGHT_RISK_IRRIGATE_THRESHOLD=float(
                os.getenv("DROUGHT_RISK_IRRIGATE_THRESHOLD", 0.50)
            ),
            CRITICAL_CLIMATE_HAZARD_THRESHOLD=float(
                os.getenv("CRITICAL_CLIMATE_HAZARD_THRESHOLD", 0.80)
            ),
            DEFAULT_IRRIGATION_DURATION_MINUTES=float(
                os.getenv("DEFAULT_IRRIGATION_DURATION_MINUTES", 30.0)
            ),
        )


@lru_cache()
def get_decision_settings() -> DecisionSettings:
    """Return cached singleton DecisionSettings instance."""
    return DecisionSettings.load_from_env()
