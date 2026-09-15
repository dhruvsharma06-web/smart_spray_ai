"""
Abstract base class for nutrient deficiency detection models.
"""

from abc import abstractmethod
from typing import Optional
from ..base import BaseVisionModel
from ...config.settings import get_settings
from ...inference.image_loader import ImageInput
from ...schemas.nutrient import NutrientDeficiencyResult


class BaseNutrientDetector(BaseVisionModel):
    """
    Abstract interface for nutrient deficiency diagnostic engines.
    """

    def __init__(self):
        self.settings = get_settings()

    @abstractmethod
    def detect(self, image: ImageInput) -> NutrientDeficiencyResult:
        """
        Assess visual nutrient deficiency indicators from plant foliage image.

        Args:
            image: ImageInput (PIL Image, file path, bytes, or base64)

        Returns:
            NutrientDeficiencyResult distinguishing visual indicators from confirmed lab tests.
        """
        pass

    def predict(self, image: ImageInput, **kwargs) -> NutrientDeficiencyResult:
        """Conform to BaseVisionModel generic predict contract."""
        return self.detect(image)
