"""
Disease detection module and factory.
Provides access to crop-aware disease detectors, registries, and adapters.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from .base import BaseDiseaseDetector
from .adapter import DiseaseModelAdapter
from .mock_disease import MockDiseaseDetector
from .registry import CropDiseaseRegistry, get_disease_registry
from ...config.settings import get_settings

logger = logging.getLogger(__name__)

__all__ = [
    "BaseDiseaseDetector",
    "DiseaseModelAdapter",
    "MockDiseaseDetector",
    "CropDiseaseRegistry",
    "get_disease_registry",
    "get_disease_detector",
]


def get_disease_detector(
    mode: Optional[str] = None,
    weights_path: Optional[str | Path] = None,
    registry: Optional[CropDiseaseRegistry] = None,
) -> BaseDiseaseDetector:
    """
    Factory to instantiate the appropriate disease detector.

    Args:
        mode: 'auto', 'mock', or 'real'.
        weights_path: Optional path to trained neural network weights file.
        registry: Optional custom CropDiseaseRegistry instance.

    Returns:
        Instance conforming to BaseDiseaseDetector.
    """
    settings = get_settings()
    selected_mode = mode or os.getenv("DISEASE_DETECTOR_MODE", "auto")

    if selected_mode == "mock":
        return MockDiseaseDetector(registry=registry)

    effective_weights = weights_path or os.getenv("DISEASE_MODEL_PATH")

    if selected_mode == "real":
        return DiseaseModelAdapter(weights_path=effective_weights, registry=registry)

    # In 'auto' mode: Check if trained weights exist on disk
    if effective_weights and Path(effective_weights).is_file():
        try:
            return DiseaseModelAdapter(weights_path=effective_weights, registry=registry)
        except Exception as e:
            logger.warning(f"Failed to load disease weights ({e}). Falling back to MockDiseaseDetector.")
            return MockDiseaseDetector(registry=registry)
    else:
        logger.info("No trained disease weights found. Using MockDiseaseDetector for local operation.")
        return MockDiseaseDetector(registry=registry)
