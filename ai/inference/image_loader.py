"""
Robust image loading, validation, and conversion utility.
Supports paths, PIL Images, raw byte buffers, and Base64 encoded images.
"""

import base64
import io
from pathlib import Path
from typing import Union
from PIL import Image

ImageInput = Union[str, Path, bytes, Image.Image]


class ImageLoader:
    """Standardized image reader and preprocessor for vision models."""

    @classmethod
    def load(cls, image_input: ImageInput) -> Image.Image:
        """
        Load and normalize any image input into an RGB PIL Image.

        Args:
            image_input: File path, Path object, raw bytes, base64 string, or PIL Image.

        Returns:
            Normalized RGB PIL Image.
        """
        if isinstance(image_input, Image.Image):
            pil_img = image_input
        elif isinstance(image_input, (str, Path)):
            path = Path(image_input)
            if not path.is_file():
                # Check if it's a base64 string
                if isinstance(image_input, str) and (
                    image_input.startswith("data:image") or len(image_input) > 256
                ):
                    return cls._load_from_base64(image_input)
                raise FileNotFoundError(f"Image file does not exist: {path}")
            pil_img = Image.open(path)
        elif isinstance(image_input, bytes):
            pil_img = Image.open(io.BytesIO(image_input))
        else:
            raise TypeError(f"Unsupported image input type: {type(image_input)}")

        # Normalize to RGB mode (stripping alpha or grayscale if needed)
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")

        return pil_img

    @classmethod
    def to_bytes(cls, image_input: ImageInput, format: str = "JPEG", quality: int = 90) -> bytes:
        """Convert input image into compressed byte array."""
        pil_img = cls.load(image_input)
        buffer = io.BytesIO()
        pil_img.save(buffer, format=format, quality=quality)
        return buffer.getvalue()

    @classmethod
    def to_base64(cls, image_input: ImageInput, format: str = "JPEG") -> str:
        """Convert input image into base64 encoded string."""
        raw_bytes = cls.to_bytes(image_input, format=format)
        return base64.b64encode(raw_bytes).decode("utf-8")

    @classmethod
    def _load_from_base64(cls, b64_str: str) -> Image.Image:
        """Decode base64 string into PIL Image."""
        if "," in b64_str:
            # Strip data:image/...;base64, prefix
            b64_str = b64_str.split(",", 1)[1]
        raw_bytes = base64.b64decode(b64_str)
        pil_img = Image.open(io.BytesIO(raw_bytes))
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        return pil_img
