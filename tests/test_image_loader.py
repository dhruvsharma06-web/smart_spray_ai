"""
Tests for ImageLoader utility.
Verifies cross-format support: file paths, PIL Images, byte buffers, and Base64.
"""

from pathlib import Path
import pytest
from PIL import Image

from ai.inference.image_loader import ImageLoader


def test_image_loader_from_pil(sample_pil_image):
    """Test loading directly from PIL Image."""
    loaded = ImageLoader.load(sample_pil_image)
    assert isinstance(loaded, Image.Image)
    assert loaded.mode == "RGB"
    assert loaded.size == (128, 128)


def test_image_loader_from_path(sample_tomato_image_path):
    """Test loading from file path."""
    loaded = ImageLoader.load(sample_tomato_image_path)
    assert isinstance(loaded, Image.Image)
    assert loaded.mode == "RGB"


def test_image_loader_from_bytes(sample_pil_image):
    """Test loading from raw JPEG bytes."""
    raw_bytes = ImageLoader.to_bytes(sample_pil_image, format="JPEG")
    assert isinstance(raw_bytes, bytes)
    assert len(raw_bytes) > 0

    reloaded = ImageLoader.load(raw_bytes)
    assert isinstance(reloaded, Image.Image)
    assert reloaded.mode == "RGB"


def test_image_loader_from_base64(sample_pil_image):
    """Test loading from base64 string with and without data URI header."""
    b64_str = ImageLoader.to_base64(sample_pil_image)
    assert isinstance(b64_str, str)

    # Decode raw base64
    loaded1 = ImageLoader.load(b64_str)
    assert loaded1.size == (128, 128)

    # Decode data URI formatted base64
    data_uri = f"data:image/jpeg;base64,{b64_str}"
    loaded2 = ImageLoader.load(data_uri)
    assert loaded2.size == (128, 128)


def test_image_loader_mode_conversion():
    """Test RGBA conversion to RGB."""
    rgba_img = Image.new("RGBA", (64, 64), color=(255, 0, 0, 128))
    converted = ImageLoader.load(rgba_img)
    assert converted.mode == "RGB"


def test_image_loader_file_not_found():
    """Test error handling for non-existent file."""
    with pytest.raises(FileNotFoundError):
        ImageLoader.load("non_existent_crop_image_9999.jpg")
