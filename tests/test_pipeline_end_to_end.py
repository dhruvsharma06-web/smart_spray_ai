"""
End-to-End Pipeline Tests for analyze_field().
"""

import pytest

from ai.inference.analyze_field import analyze_field
from ai.schemas.pipeline import FieldAnalysisOutput


def test_analyze_field_end_to_end_tomato(sample_tomato_early_blight_path):
    """
    Test end-to-end analyze_field pipeline with sample tomato early blight image
    and mock sensor/weather telemetry.
    """
    mock_sensors = {
        "soil": {"moisture_percent": 18.0, "temperature_celsius": 29.0},
        "air": {"temperature_celsius": 36.0, "humidity_percent": 30.0, "rainfall_mm": 0.0},
    }
    mock_weather = {"upcoming_24h_rainfall_mm": 0.0}

    result = analyze_field(
        image=sample_tomato_early_blight_path,
        sensor_data=mock_sensors,
        weather_data=mock_weather,
        crop_stage="fruiting",
        explainer_mode="mock",
    )

    assert isinstance(result, FieldAnalysisOutput)
    # Check Crop Block
    assert result.crop.name == "tomato"
    assert result.crop.confidence >= 0.0

    # Check Disease Block
    assert result.disease is not None
    assert result.disease.name == "early_blight"

    # Check Severity Block
    assert result.severity is not None
    assert result.severity.level in ["healthy", "low", "moderate", "high", "critical"]

    # Check Climate Risk Block
    assert result.climate_risk.drought > 0.5  # Moisture 18% + high temp -> drought risk

    # Check Metadata & GenAI explanation
    assert "metadata" in result.model_dump()
    meta = result.metadata
    assert "explanation" in meta
    assert "what_detected" in meta["explanation"]["sections"]
    assert "recommended_action" in meta["explanation"]["sections"]


def test_analyze_field_low_confidence_trigger(sample_low_conf_image_path):
    """
    Test that low confidence inputs properly flag requires_confirmation=True.
    """
    result = analyze_field(
        image=sample_low_conf_image_path,
        explainer_mode="mock",
    )

    assert isinstance(result, FieldAnalysisOutput)
    assert result.requires_confirmation is True
