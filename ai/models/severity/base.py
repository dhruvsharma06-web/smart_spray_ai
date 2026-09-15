"""
Abstract base class for Severity Assessment engines.
"""

from abc import abstractmethod
from typing import Optional
from ..base import BaseVisionModel
from ...config.settings import get_settings
from ...inference.image_loader import ImageInput
from ...schemas.disease import DiseaseDetectionResult
from ...schemas.nutrient import NutrientDeficiencyResult
from ...schemas.pest import PestDetectionResult
from ...schemas.severity import SeverityAssessmentResult


class BaseSeverityEstimator(BaseVisionModel):
    """
    Abstract interface for severity estimation components.
    """

    def __init__(self):
        self.settings = get_settings()

    @abstractmethod
    def estimate(
        self,
        image: Optional[ImageInput] = None,
        disease: Optional[DiseaseDetectionResult] = None,
        pest: Optional[PestDetectionResult] = None,
        nutrient: Optional[NutrientDeficiencyResult] = None,
    ) -> SeverityAssessmentResult:
        """
        Estimate composite damage severity from disease, pest, and nutrient diagnostic outputs.
        """
        pass

    def predict(self, image: ImageInput, **kwargs) -> SeverityAssessmentResult:
        """Conform to BaseVisionModel generic predict contract."""
        return self.estimate(
            image=image,
            disease=kwargs.get("disease"),
            pest=kwargs.get("pest"),
            nutrient=kwargs.get("nutrient"),
        )
