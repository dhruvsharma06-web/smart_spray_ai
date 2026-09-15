"""
Tests for Crop Identification models and factory.
Includes both deterministic mock execution and live Gemini API testing (when key is available).
"""

import os
import pytest
from PIL import Image

from ai.config.settings import get_settings
from ai.models.crop import (
    BaseCropIdentifier,
    GeminiVisionCropIdentifier,
    MockCropIdentifier,
    get_crop_identifier,
)
from ai.schemas.crop import CropIdentificationResult


def test_mock_identifier_basic(mock_crop_identifier, sample_pil_image):
    """Test standard identification with default mock values."""
    result = mock_crop_identifier.identify(sample_pil_image)

    assert isinstance(result, CropIdentificationResult)
    assert result.crop_name == "tomato"
    assert result.scientific_name == "Solanum lycopersicum"
    assert result.confidence == 0.95
    assert result.confidence_level == "high"
    assert result.requires_confirmation is False
    assert result.is_plant is True
    assert "leaves" in result.detected_parts


def test_mock_identifier_file_hints(
    mock_crop_identifier,
    sample_tomato_image_path,
    sample_maize_image_path,
    sample_low_conf_image_path,
    sample_not_plant_image_path,
):
    """Test mock identification with file hints from generated test dataset."""
    # Tomato image
    res_tomato = mock_crop_identifier.identify(sample_tomato_image_path)
    assert res_tomato.crop_name == "tomato"
    assert res_tomato.confidence >= 0.85
    assert res_tomato.requires_confirmation is False

    # Maize image
    res_maize = mock_crop_identifier.identify(sample_maize_image_path)
    assert res_maize.crop_name == "maize"
    assert res_maize.confidence >= 0.85
    assert res_maize.requires_confirmation is False

    # Low confidence image
    res_low = mock_crop_identifier.identify(sample_low_conf_image_path)
    assert res_low.confidence_level == "low"
    assert res_low.requires_confirmation is True

    # Non-plant image
    res_not_plant = mock_crop_identifier.identify(sample_not_plant_image_path)
    assert res_not_plant.is_plant is False
    assert res_not_plant.requires_confirmation is True


def test_crop_identifier_factory():
    """Verify factory behavior under different modes."""
    # Explicit mock
    ident_mock = get_crop_identifier(mode="mock")
    assert isinstance(ident_mock, MockCropIdentifier)

    # Explicit gemini (without key check, checks class type)
    ident_gemini = get_crop_identifier(mode="gemini", api_key="dummy_test_key")
    assert isinstance(ident_gemini, GeminiVisionCropIdentifier)
    assert ident_gemini.api_key == "dummy_test_key"

    # Auto mode without key should safely return MockCropIdentifier
    if not os.getenv("GEMINI_API_KEY"):
        ident_auto = get_crop_identifier(mode="auto")
        assert isinstance(ident_auto, MockCropIdentifier)


@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY environment variable not set; skipping live vision API call.",
)
def test_live_gemini_vision_crop_identification(sample_tomato_image_path):
    """
    Live test against Gemini 3.8 Flash model using Google GenAI SDK.
    Runs only when valid GEMINI_API_KEY is configured.
    """
    identifier = GeminiVisionCropIdentifier()
    result = identifier.identify(sample_tomato_image_path)

    assert isinstance(result, CropIdentificationResult)
    assert result.is_plant is True
    assert result.confidence > 0.0
    assert result.crop_name != ""
    assert result.confidence_level in ["high", "moderate", "low"]
