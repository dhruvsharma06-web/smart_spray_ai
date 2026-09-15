"""
Tests for confidence-aware governance rules.
Verifies threshold enforcement (high >=0.85, mod 0.60-0.85, low <0.60),
and safety gating (requires_confirmation = True for low confidence or non-plant).
"""

import pytest
from ai.config.settings import get_settings
from ai.models.crop.mock_crop import MockCropIdentifier


def test_confidence_tiers_and_confirmation():
    """Verify standard confidence levels per project specification."""
    settings = get_settings()

    # Test high confidence (>= 0.85)
    assert settings.get_confidence_level(0.95) == "high"
    assert settings.get_confidence_level(0.85) == "high"
    assert settings.is_confirmation_required(0.85) is False

    # Test moderate confidence (0.60 <= score < 0.85)
    assert settings.get_confidence_level(0.84) == "moderate"
    assert settings.get_confidence_level(0.60) == "moderate"
    assert settings.is_confirmation_required(0.60) is False

    # Test low confidence (< 0.60)
    assert settings.get_confidence_level(0.59) == "low"
    assert settings.get_confidence_level(0.40) == "low"
    assert settings.get_confidence_level(0.10) == "low"
    assert settings.is_confirmation_required(0.59) is True
    assert settings.is_confirmation_required(0.20) is True


def test_mock_identifier_enforces_requires_confirmation(mock_crop_identifier, sample_pil_image):
    """Verify that MockCropIdentifier applies requires_confirmation properly."""
    # High confidence run
    res_high = mock_crop_identifier.identify(sample_pil_image, override_confidence=0.92)
    assert res_high.confidence_level == "high"
    assert res_high.requires_confirmation is False

    # Moderate confidence run
    res_mod = mock_crop_identifier.identify(sample_pil_image, override_confidence=0.72)
    assert res_mod.confidence_level == "moderate"
    assert res_mod.requires_confirmation is False

    # Low confidence run
    res_low = mock_crop_identifier.identify(sample_pil_image, override_confidence=0.48)
    assert res_low.confidence_level == "low"
    assert res_low.requires_confirmation is True
    assert len(res_low.alternative_candidates) > 0

    # Non-plant run
    res_not_plant = mock_crop_identifier.identify(
        sample_pil_image,
        override_is_plant=False,
        override_confidence=0.15,
    )
    assert res_not_plant.is_plant is False
    assert res_not_plant.requires_confirmation is True
