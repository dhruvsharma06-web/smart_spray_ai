"""
Abstract base class for pest detection models.
Enforces standard pest detection interfaces and confidence governance.
"""

from abc import abstractmethod
from typing import Optional
from ..base import BaseVisionModel
from ...config.settings import get_settings
from ...inference.image_loader import ImageInput
from ...schemas.pest import PestDetectionResult


class BasePestDetector(BaseVisionModel):
    """
    Abstract interface for all pest detection backends
    (e.g., YOLO detection, ONNX, Mock).
    """

    def __init__(self):
        self.settings = get_settings()

    @abstractmethod
    def detect(self, image: ImageInput) -> PestDetectionResult:
        """
        Detect pest instances, counts, and bounding boxes in foliage image.

        Args:
            image: ImageInput (PIL Image, file path, bytes, or base64)

        Returns:
            PestDetectionResult with list of DetectedPest objects, count, and severity.
        """
        pass

    def predict(self, image: ImageInput, **kwargs) -> PestDetectionResult:
        """Conform to BaseVisionModel generic predict contract."""
        return self.detect(image)
