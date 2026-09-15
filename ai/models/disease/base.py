"""
Abstract base class for disease detection models.
Enforces crop-aware routing, standard inputs/outputs, and confidence governance.
"""

from abc import abstractmethod
from typing import Optional
from ..base import BaseVisionModel
from ...config.settings import get_settings
from ...inference.image_loader import ImageInput
from ...schemas.disease import DiseaseDetectionResult
from .registry import CropDiseaseRegistry, get_disease_registry


class BaseDiseaseDetector(BaseVisionModel):
    """
    Abstract interface for all disease detection backends
    (e.g., PyTorch classification, YOLO detection, ONNX, Mock).
    """

    def __init__(self, registry: Optional[CropDiseaseRegistry] = None):
        self.registry = registry or get_disease_registry()
        self.settings = get_settings()

    @abstractmethod
    def detect(self, image: ImageInput, crop: Optional[str] = None) -> DiseaseDetectionResult:
        """
        Diagnose disease on the given foliage image with crop context.

        Args:
            image: ImageInput (PIL Image, file path, bytes, or base64)
            crop: Optional crop name from Phase 1 crop identification (e.g. 'tomato', 'potato')

        Returns:
            DiseaseDetectionResult containing diagnosed disease, confidence,
            confirmation flag, and any localized bounding boxes.
        """
        pass

    def predict(self, image: ImageInput, **kwargs) -> DiseaseDetectionResult:
        """Conform to BaseVisionModel generic predict contract."""
        crop = kwargs.get("crop")
        return self.detect(image, crop=crop)
