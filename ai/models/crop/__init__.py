"""
Crop identification package and factory.
Provides seamless switching between open-world Gemini multimodal vision and local mock models.
"""

import logging
import os
from typing import Optional

from .base import BaseCropIdentifier
from .gemini_vision import GeminiVisionCropIdentifier
from .mock_crop import MockCropIdentifier
from ...config.settings import get_settings

logger = logging.getLogger(__name__)

__all__ = [
    "BaseCropIdentifier",
    "GeminiVisionCropIdentifier",
    "MockCropIdentifier",
    "get_crop_identifier",
]


def get_crop_identifier(
    mode: Optional[str] = None,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
) -> BaseCropIdentifier:
    """
    Factory to instantiate the appropriate crop identifier.

    Args:
        mode: 'auto', 'gemini', or 'mock'. If None, uses settings.CROP_IDENTIFIER_MODE.
        api_key: Optional Gemini API key override.
        model_name: Optional Gemini model name override (defaults to gemini-3.8-flash).

    Returns:
        Instance conforming to BaseCropIdentifier.
    """
    settings = get_settings()
    selected_mode = mode or settings.CROP_IDENTIFIER_MODE

    if selected_mode == "mock":
        return MockCropIdentifier()

    effective_key = api_key or settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")

    if selected_mode == "gemini":
        return GeminiVisionCropIdentifier(api_key=effective_key, model_name=model_name)

    # In 'auto' mode: Use Gemini if API key is present; otherwise fall back to mock
    if effective_key:
        try:
            return GeminiVisionCropIdentifier(api_key=effective_key, model_name=model_name)
        except Exception as e:
            logger.warning(
                f"Failed to initialize GeminiVisionCropIdentifier ({e}). Falling back to MockCropIdentifier."
            )
            return MockCropIdentifier()
    else:
        logger.info("No GEMINI_API_KEY detected. Using deterministic MockCropIdentifier for offline operation.")
        return MockCropIdentifier()
