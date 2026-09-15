"""
Abstract base class for crop and plant identification models.
"""

from abc import abstractmethod
from ..base import BaseVisionModel
from ...inference.image_loader import ImageInput
from ...schemas.crop import CropIdentificationResult


class BaseCropIdentifier(BaseVisionModel):
    """Abstract interface for crop identification components."""

    @abstractmethod
    def identify(self, image: ImageInput) -> CropIdentificationResult:
        """
        Identify plant species/crop from image input.

        Args:
            image: ImageInput (PIL Image, file path, bytes, or base64)

        Returns:
            CropIdentificationResult with confidence ratings and botanical metadata.
        """
        pass

    def predict(self, image: ImageInput, **kwargs) -> CropIdentificationResult:
        """Alias conforming to BaseVisionModel."""
        return self.identify(image)
