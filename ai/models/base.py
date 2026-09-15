"""
Base abstract interfaces for all computer vision models.
Ensures clean swapping of underlying models (e.g. YOLO, PyTorch, GenAI, ONNX).
"""

from abc import ABC, abstractmethod
from typing import Any, Union, TYPE_CHECKING
from pathlib import Path
from PIL import Image

if TYPE_CHECKING:
    from ..inference.image_loader import ImageInput
else:
    ImageInput = Any


class BaseVisionModel(ABC):
    """Abstract base class for vision and diagnosis models."""

    @abstractmethod
    def predict(self, image: ImageInput, **kwargs: Any) -> Any:
        """Execute model inference on the provided image input."""
        pass
