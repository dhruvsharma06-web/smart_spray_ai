"""
Pest detection package and factory.
Provides access to pest detection models, mock engines, and adapters.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from .base import BasePestDetector
from .adapter import PestModelAdapter
from .mock_pest import MockPestDetector
from ...config.settings import get_settings

logger = logging.getLogger(__name__)

__all__ = [
    "BasePestDetector",
    "PestModelAdapter",
    "MockPestDetector",
    "get_pest_detector",
]


def get_pest_detector(
    mode: Optional[str] = None,
    weights_path: Optional[str | Path] = None,
) -> BasePestDetector:
    """
    Factory to instantiate the appropriate pest detector.

    Args:
        mode: 'auto', 'mock', or 'real'.
        weights_path: Optional path to trained pest weights file.

    Returns:
        Instance conforming to BasePestDetector.
    """
    settings = get_settings()
    selected_mode = mode or os.getenv("PEST_DETECTOR_MODE", "auto")

    if selected_mode == "mock":
        return MockPestDetector()

    effective_weights = weights_path or getattr(settings, "PEST_MODEL_PATH", None) or os.getenv("PEST_MODEL_PATH")

    if selected_mode == "real":
        return PestModelAdapter(weights_path=effective_weights)

    # In 'auto' mode: Check if trained weights exist on disk
    if effective_weights and Path(effective_weights).is_file():
        try:
            return PestModelAdapter(weights_path=effective_weights)
        except Exception as e:
            logger.warning(f"Failed to load pest weights ({e}). Falling back to MockPestDetector.")
            return MockPestDetector()
    else:
        logger.info("No trained pest weights found. Using MockPestDetector for local operation.")
        return MockPestDetector()
