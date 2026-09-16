import pytest
import pytest_asyncio
import httpx
import uuid
from unittest.mock import AsyncMock, patch
from app.schemas.ai_response import validate_ai_response, AnalysisResult
from pydantic import ValidationError


class TestAIResponseValidation:
    """Tests for AI response validation schema."""

    def test_valid_minimal_response(self):
        """Test validation of minimal valid AI response."""
        response = {
            "crop": {"name": "tomato", "confidence": 0.96},
            "pests": [],
            "climate_risk": {"drought": 0.2, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05},
            "requires_confirmation": False
        }
        result = validate_ai_response(response)
        assert isinstance(result, AnalysisResult)
        assert result.crop.name == "tomato"
        assert result.crop.confidence == 0.96

    def test_valid_full_response(self):
        """Test validation of full AI response with all fields."""
        response = {
            "crop": {"name": "tomato", "confidence": 0.96},
            "disease": {"name": "early_blight", "confidence": 0.94, "severity": "moderate", "affected_area_percent": 18.5},
            "pests": [
                {"name": "aphid", "confidence": 0.87, "count": 5, "detections": {"bbox": [10, 20, 30, 40]}}
            ],
            "nutrient_deficiency": {"nitrogen": 0.3},
            "severity": {"level": "moderate", "affected_area_percent": 18.5},
            "climate_risk": {"drought": 0.78, "heat": 0.84, "flood": 0.12, "waterlogging": 0.25},
            "requires_confirmation": False
        }
        result = validate_ai_response(response)
        assert isinstance(result, AnalysisResult)
        assert result.disease is not None
        assert result.disease.name == "early_blight"
        assert len(result.pests) == 1
        assert result.pests[0].name == "aphid"

    def test_missing_crop_name_rejected(self):
        """Missing crop.name should be rejected."""
        response = {
            "crop": {"confidence": 0.96},
            "pests": [],
            "climate_risk": {"drought": 0.2, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05}
        }
        with pytest.raises(ValidationError) as exc:
            validate_ai_response(response)
        assert "crop.name" in str(exc.value)

    def test_empty_crop_name_rejected(self):
        """Empty crop.name should be rejected."""
        response = {
            "crop": {"name": "", "confidence": 0.96},
            "pests": [],
            "climate_risk": {"drought": 0.2, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05}
        }
        with pytest.raises(ValidationError) as exc:
            validate_ai_response(response)
        assert "crop.name" in str(exc.value)

    def test_confidence_out_of_range_rejected(self):
        """Confidence > 1.0 should be rejected."""
        response = {
            "crop": {"name": "tomato", "confidence": 1.5},
            "pests": [],
            "climate_risk": {"drought": 0.2, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05}
        }
        with pytest.raises(ValidationError) as exc:
            validate_ai_response(response)
        assert "confidence" in str(exc.value)

    def test_negative_confidence_rejected(self):
        """Negative confidence should be rejected."""
        response = {
            "crop": {"name": "tomato", "confidence": -0.1},
            "pests": [],
            "climate_risk": {"drought": 0.2, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05}
        }
        with pytest.raises(ValidationError) as exc:
            validate_ai_response(response)
        assert "confidence" in str(exc.value)

    def test_climate_risk_out_of_range_rejected(self):
        """Climate risk > 1.0 should be rejected."""
        response = {
            "crop": {"name": "tomato", "confidence": 0.96},
            "pests": [],
            "climate_risk": {"drought": 1.5, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05}
        }
        with pytest.raises(ValidationError) as exc:
            validate_ai_response(response)
        assert "drought" in str(exc.value)

    def test_missing_climate_risk_rejected(self):
        """Missing climate_risk should be rejected."""
        response = {
            "crop": {"name": "tomato", "confidence": 0.96},
            "pests": []
        }
        with pytest.raises(ValidationError) as exc:
            validate_ai_response(response)
        assert "climate_risk" in str(exc.value)

    def test_missing_pests_allowed(self):
        """Missing pests should default to empty list."""
        response = {
            "crop": {"name": "tomato", "confidence": 0.96},
            "climate_risk": {"drought": 0.2, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05}
        }
        result = validate_ai_response(response)
        assert result.pests == []

    def test_disease_null_allowed(self):
        """Null disease should be allowed."""
        response = {
            "crop": {"name": "tomato", "confidence": 0.96},
            "disease": None,
            "pests": [],
            "climate_risk": {"drought": 0.2, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05}
        }
        result = validate_ai_response(response)
        assert result.disease is None

    def test_disease_empty_name_becomes_none(self):
        """Empty disease name should become None."""
        response = {
            "crop": {"name": "tomato", "confidence": 0.96},
            "disease": {"name": "", "confidence": 0.5},
            "pests": [],
            "climate_risk": {"drought": 0.2, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05}
        }
        result = validate_ai_response(response)
        # Empty name becomes None, so disease is effectively None
        assert result.disease is not None
        assert result.disease.name is None

    def test_pest_missing_name_rejected(self):
        """Pest without name should be rejected."""
        response = {
            "crop": {"name": "tomato", "confidence": 0.96},
            "pests": [{"confidence": 0.8}],
            "climate_risk": {"drought": 0.2, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05}
        }
        with pytest.raises(ValidationError) as exc:
            validate_ai_response(response)
        assert "pests" in str(exc.value)

    def test_extra_fields_allowed(self):
        """Extra fields should be allowed (forward compatibility)."""
        response = {
            "crop": {"name": "tomato", "confidence": 0.96},
            "pests": [],
            "climate_risk": {"drought": 0.2, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05},
            "extra_field": "should_be_ignored",
            "model_version": "2.0"
        }
        result = validate_ai_response(response)
        assert result.crop.name == "tomato"

    def test_severity_optional_fields(self):
        """Severity with only level or only affected_area_percent should work."""
        response = {
            "crop": {"name": "tomato", "confidence": 0.96},
            "pests": [],
            "climate_risk": {"drought": 0.2, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05},
            "severity": {"level": "high"}
        }
        result = validate_ai_response(response)
        assert result.severity.level == "high"
        assert result.severity.affected_area_percent is None

    def test_disease_confidence_optional(self):
        """Disease without confidence should be allowed."""
        response = {
            "crop": {"name": "tomato", "confidence": 0.96},
            "disease": {"name": "early_blight"},
            "pests": [],
            "climate_risk": {"drought": 0.2, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05}
        }
        result = validate_ai_response(response)
        assert result.disease.name == "early_blight"
        assert result.disease.confidence is None