"""
Tests for domain schemas and contracts.
Verifies serialization, deserialization, and alignment with Person 2's Decision Engine.
"""

import json
import pytest
from pydantic import ValidationError

from ai.schemas.crop import CropIdentificationResult, AlternativeCropCandidate
from ai.schemas.pipeline import (
    FieldAnalysisOutput,
    CropSummary,
    DiseaseSummary,
    SeveritySummary,
    ClimateRiskSummary,
)


def test_crop_identification_result_valid():
    """Test valid instantiation and name normalization."""
    result = CropIdentificationResult(
        crop_name="  Tomato  ",
        scientific_name="Solanum lycopersicum",
        confidence=0.96,
        confidence_level="high",
        requires_confirmation=False,
        detected_parts=["leaves", "fruit"],
        growth_stage_visual="fruiting",
        is_plant=True,
        reasoning="Pinnate compound leaves and lobed red fruit characteristic of tomato.",
    )
    # Checks lowercase normalization
    assert result.crop_name == "tomato"
    assert result.confidence == 0.96
    assert result.confidence_level == "high"
    assert result.requires_confirmation is False
    assert "leaves" in result.detected_parts


def test_crop_identification_result_invalid_confidence():
    """Test confidence bounds enforcement."""
    with pytest.raises(ValidationError):
        CropIdentificationResult(
            crop_name="tomato",
            confidence=1.5,  # Invalid: > 1.0
            confidence_level="high",
            requires_confirmation=False,
        )

    with pytest.raises(ValidationError):
        CropIdentificationResult(
            crop_name="tomato",
            confidence=-0.1,  # Invalid: < 0.0
            confidence_level="low",
            requires_confirmation=True,
        )


def test_field_analysis_output_contract_exact_match():
    """
    Test that FieldAnalysisOutput strictly serializes into the exact schema
    demanded by the Decision Engine specifications.
    """
    payload = FieldAnalysisOutput(
        crop=CropSummary(name="tomato", confidence=0.96),
        disease=DiseaseSummary(name="early_blight", confidence=0.92),
        pests=[],
        nutrient_deficiency=None,
        severity=SeveritySummary(level="moderate", affected_area_percent=18.0),
        climate_risk=ClimateRiskSummary(
            drought=0.78,
            heat=0.84,
            flood=0.12,
            waterlogging=0.25,
        ),
        requires_confirmation=False,
    )

    serialized = payload.model_dump(exclude_none=False, exclude={"metadata"})
    expected = {
        "crop": {"name": "tomato", "confidence": 0.96},
        "disease": {"name": "early_blight", "confidence": 0.92},
        "pests": [],
        "nutrient_deficiency": None,
        "severity": {"level": "moderate", "affected_area_percent": 18.0},
        "climate_risk": {
            "drought": 0.78,
            "heat": 0.84,
            "flood": 0.12,
            "waterlogging": 0.25,
        },
        "requires_confirmation": False,
    }

    assert serialized == expected
    # Verify it can be converted to JSON string and back
    json_str = payload.model_dump_json()
    assert json.loads(json_str)["crop"]["name"] == "tomato"
