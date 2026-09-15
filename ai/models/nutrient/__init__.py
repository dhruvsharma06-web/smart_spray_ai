"""
Nutrient deficiency detection package and factory.
"""

from typing import Optional
from .base import BaseNutrientDetector
from .mock_nutrient import MockNutrientDetector

__all__ = [
    "BaseNutrientDetector",
    "MockNutrientDetector",
    "get_nutrient_detector",
]


def get_nutrient_detector(mode: Optional[str] = None) -> BaseNutrientDetector:
    """
    Factory to instantiate nutrient deficiency detector.
    Defaults to MockNutrientDetector as robust fallback.
    """
    return MockNutrientDetector()
