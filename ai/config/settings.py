"""
Central settings for the AI/ML module.
Manages confidence thresholds, model selections, API keys, and environment overrides.
"""

from functools import lru_cache
import os
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv

# Automatically look for .env file in project root or current directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class AISettings:
    """Settings and hyperparameter configuration for AI services."""

    # Confidence Thresholds
    HIGH_CONFIDENCE_THRESHOLD: float = 0.85
    LOW_CONFIDENCE_THRESHOLD: float = 0.60

    # Model configuration
    # Default to modern gemini-3.8-flash per Google GenAI SDK standards
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")

    # Crop identifier mode: 'auto' (detects API key), 'gemini', or 'mock'
    CROP_IDENTIFIER_MODE: Literal["auto", "gemini", "mock"] = os.getenv(
        "CROP_IDENTIFIER_MODE", "auto"
    )  # type: ignore

    # Disease detector mode and weights
    DISEASE_MODEL_PATH: str | None = os.getenv("DISEASE_MODEL_PATH")
    DISEASE_DETECTOR_MODE: Literal["auto", "mock", "real"] = os.getenv(
        "DISEASE_DETECTOR_MODE", "auto"
    )  # type: ignore

    # Directories
    ROOT_DIR: Path = PROJECT_ROOT
    DATA_DIR: Path = PROJECT_ROOT / "ai" / "data"
    SAMPLE_IMAGES_DIR: Path = PROJECT_ROOT / "ai" / "data" / "sample_images"
    MOCK_SENSORS_DIR: Path = PROJECT_ROOT / "ai" / "data" / "mock_sensors"
    MOCK_WEATHER_DIR: Path = PROJECT_ROOT / "ai" / "data" / "mock_weather"

    def get_confidence_level(self, score: float) -> Literal["high", "moderate", "low"]:
        """Determine qualitative confidence tier based on numerical score."""
        if score >= self.HIGH_CONFIDENCE_THRESHOLD:
            return "high"
        elif score >= self.LOW_CONFIDENCE_THRESHOLD:
            return "moderate"
        else:
            return "low"

    def is_confirmation_required(self, score: float) -> bool:
        """Determine if low confidence requires human confirmation."""
        return score < self.LOW_CONFIDENCE_THRESHOLD


@lru_cache()
def get_settings() -> AISettings:
    """Return cached singleton settings instance."""
    return AISettings()
