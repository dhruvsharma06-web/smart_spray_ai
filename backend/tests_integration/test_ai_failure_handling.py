import pytest
import pytest_asyncio
import httpx
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import TimeoutException, ConnectError, HTTPStatusError, Response
from app.ai.client import AIService
from app.schemas.ai_response import validate_ai_response, AnalysisResult
from pydantic import ValidationError


class TestAIClientFailureHandling:
    """Tests for AI client failure handling."""

    @pytest_asyncio.fixture
    def ai_service(self):
        return AIService(base_url="http://test-ai:8001")

    @pytest.mark.asyncio
    async def test_ai_timeout_raises(self, ai_service):
        """AI timeout should raise TimeoutException."""
        ai_service._client.post = AsyncMock(side_effect=TimeoutException("Timeout"))
        
        with pytest.raises(TimeoutException):
            await ai_service.analyze(
                b"fake image", "test.jpg",
                {"soil": {}}, {"temperature": 25},
                "flowering"
            )

    @pytest.mark.asyncio
    async def test_ai_connection_error_raises(self, ai_service):
        """AI connection error should raise ConnectError."""
        ai_service._client.post = AsyncMock(side_effect=ConnectError("Connection refused"))
        
        with pytest.raises(ConnectError):
            await ai_service.analyze(
                b"fake image", "test.jpg",
                {"soil": {}}, {"temperature": 25},
                "flowering"
            )

    @pytest.mark.asyncio
    async def test_ai_4xx_error_raises(self, ai_service):
        """AI 4xx error should raise HTTPStatusError."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        
        error = HTTPStatusError("400 Bad Request", request=MagicMock(), response=mock_response)
        ai_service._client.post = AsyncMock(side_effect=error)
        
        with pytest.raises(HTTPStatusError):
            await ai_service.analyze(
                b"fake image", "test.jpg",
                {"soil": {}}, {"temperature": 25},
                "flowering"
            )

    @pytest.mark.asyncio
    async def test_ai_5xx_error_raises(self, ai_service):
        """AI 5xx error should raise HTTPStatusError."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        
        error = HTTPStatusError("500 Internal Server Error", request=MagicMock(), response=mock_response)
        ai_service._client.post = AsyncMock(side_effect=error)
        
        with pytest.raises(HTTPStatusError):
            await ai_service.analyze(
                b"fake image", "test.jpg",
                {"soil": {}}, {"temperature": 25},
                "flowering"
            )

    @pytest.mark.asyncio
    async def test_malformed_ai_response_rejected(self, ai_service):
        """Malformed AI response should be rejected by validation."""
        # Mock the HTTP response to return invalid data
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "crop": {"confidence": 0.96},  # Missing required 'name'
            "pests": [],
            "climate_risk": {"drought": 0.2, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05}
        }
        
        ai_service._client.post = AsyncMock(return_value=mock_response)
        
        with pytest.raises(ValueError) as exc:
            await ai_service.analyze(
                b"fake image", "test.jpg",
                {"soil": {}}, {"temperature": 25},
                "flowering"
            )
        assert "validation failed" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_ai_response_with_out_of_range_confidence_rejected(self, ai_service):
        """AI response with confidence > 1.0 should be rejected."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "crop": {"name": "tomato", "confidence": 1.5},  # Invalid!
            "pests": [],
            "climate_risk": {"drought": 0.2, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05}
        }
        
        ai_service._client.post = AsyncMock(return_value=mock_response)
        
        with pytest.raises(ValueError) as exc:
            await ai_service.analyze(
                b"fake image", "test.jpg",
                {"soil": {}}, {"temperature": 25},
                "flowering"
            )
        assert "validation failed" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_ai_service_unavailable_raises(self, ai_service):
        """AI service unavailable should raise ConnectError after retries."""
        ai_service._client.post = AsyncMock(side_effect=ConnectError("Service unavailable"))
        
        with pytest.raises(ConnectError):
            await ai_service.analyze(
                b"fake image", "test.jpg",
                {"soil": {}}, {"temperature": 25},
                "flowering"
            )


class TestAIServiceIntegrationWithMock:
    """Integration tests using the actual mock AI service."""

    @pytest_asyncio.fixture
    async def ai_service(self):
        return AIService(base_url="http://mock-ai:8001")

    @pytest.mark.asyncio
    async def test_mock_ai_returns_valid_response(self, ai_service):
        """Mock AI service should return valid response."""
        result = await ai_service.analyze(
            b"fake image", "test.jpg",
            {"soil": {"moisture": 45}}, {"temperature": 25, "humidity": 60},
            "flowering"
        )
        
        assert isinstance(result, dict)
        assert "crop" in result
        assert result["crop"]["name"] == "tomato"
        assert result["crop"]["confidence"] == 0.96
        assert "disease" in result
        assert "pests" in result
        assert "climate_risk" in result

    @pytest.mark.asyncio
    async def test_mock_ai_response_passes_validation(self, ai_service):
        """Mock AI response should pass strict validation."""
        result = await ai_service.analyze(
            b"fake image", "test.jpg",
            {"soil": {}}, {"temperature": 25},
            "flowering"
        )
        
        # This should not raise
        validated = AnalysisResult.model_validate(result)
        assert validated.crop.name == "tomato"
        assert validated.crop.confidence == 0.96

    @pytest.mark.asyncio
    async def test_ai_service_with_empty_sensor_weather(self, ai_service):
        """AI service should work with empty sensor/weather data."""
        result = await ai_service.analyze(
            b"fake image", "test.jpg",
            {}, {},  # Empty sensor and weather
            ""
        )
        
        assert "crop" in result
        assert result["crop"]["name"] == "tomato"

    @pytest.mark.asyncio
    async def test_ai_service_with_none_crop_stage(self, ai_service):
        """AI service should handle None crop_stage."""
        result = await ai_service.analyze(
            b"fake image", "test.jpg",
            {"soil": {}}, {"temperature": 25},
            None
        )
        
        assert "crop" in result


class TestAIResponseMalformedScenarios:
    """Tests for various malformed AI response scenarios."""

    def test_response_missing_crop(self):
        """Response missing crop field should fail validation."""
        response = {
            "pests": [],
            "climate_risk": {"drought": 0.2, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05}
        }
        with pytest.raises(ValidationError):
            validate_ai_response(response)

    def test_response_crop_not_object(self):
        """Crop as string instead of object should fail."""
        response = {
            "crop": "tomato",  # Should be object
            "pests": [],
            "climate_risk": {"drought": 0.2, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05}
        }
        with pytest.raises(ValidationError):
            validate_ai_response(response)

    def test_response_pests_not_list(self):
        """Pests as object instead of list should fail."""
        response = {
            "crop": {"name": "tomato", "confidence": 0.96},
            "pests": {"name": "aphid"},  # Should be list
            "climate_risk": {"drought": 0.2, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05}
        }
        with pytest.raises(ValidationError):
            validate_ai_response(response)

    def test_response_climate_risk_not_object(self):
        """Climate risk as array instead of object should fail."""
        response = {
            "crop": {"name": "tomato", "confidence": 0.96},
            "pests": [],
            "climate_risk": [0.2, 0.3, 0.1, 0.05]  # Should be object
        }
        with pytest.raises(ValidationError):
            validate_ai_response(response)

    def test_disease_confidence_out_of_range(self):
        """Disease confidence > 1.0 should fail."""
        response = {
            "crop": {"name": "tomato", "confidence": 0.96},
            "disease": {"name": "early_blight", "confidence": 2.0},
            "pests": [],
            "climate_risk": {"drought": 0.2, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05}
        }
        with pytest.raises(ValidationError):
            validate_ai_response(response)

    def test_pest_confidence_out_of_range(self):
        """Pest confidence > 1.0 should fail."""
        response = {
            "crop": {"name": "tomato", "confidence": 0.96},
            "pests": [{"name": "aphid", "confidence": 1.5}],
            "climate_risk": {"drought": 0.2, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05}
        }
        with pytest.raises(ValidationError):
            validate_ai_response(response)

    def test_severity_affected_area_out_of_range(self):
        """Severity affected_area_percent > 100 should fail."""
        response = {
            "crop": {"name": "tomato", "confidence": 0.96},
            "pests": [],
            "climate_risk": {"drought": 0.2, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05},
            "severity": {"level": "high", "affected_area_percent": 150.0}
        }
        with pytest.raises(ValidationError):
            validate_ai_response(response)

    def test_valid_disease_with_all_fields(self):
        """Disease with all optional fields should pass."""
        response = {
            "crop": {"name": "tomato", "confidence": 0.96},
            "disease": {
                "name": "early_blight",
                "confidence": 0.94,
                "severity": "moderate",
                "affected_area_percent": 18.5
            },
            "pests": [],
            "climate_risk": {"drought": 0.2, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05}
        }
        result = validate_ai_response(response)
        assert result.disease.name == "early_blight"
        assert result.disease.confidence == 0.94
        assert result.disease.severity == "moderate"
        assert result.disease.affected_area_percent == 18.5

    def test_pest_with_all_fields(self):
        """Pest with all optional fields should pass."""
        response = {
            "crop": {"name": "tomato", "confidence": 0.96},
            "pests": [{
                "name": "aphid",
                "confidence": 0.87,
                "count": 5,
                "detections": {"bbox": [10, 20, 30, 40], "class_id": 1}
            }],
            "climate_risk": {"drought": 0.2, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05}
        }
        result = validate_ai_response(response)
        assert len(result.pests) == 1
        assert result.pests[0].name == "aphid"
        assert result.pests[0].count == 5
        assert result.pests[0].detections == {"bbox": [10, 20, 30, 40], "class_id": 1}

    def test_nutrient_deficiency_allowed(self):
        """nutrient_deficiency field should be allowed."""
        response = {
            "crop": {"name": "tomato", "confidence": 0.96},
            "pests": [],
            "climate_risk": {"drought": 0.2, "heat": 0.3, "flood": 0.1, "waterlogging": 0.05},
            "nutrient_deficiency": {"nitrogen": 0.3, "phosphorus": 0.1}
        }
        result = validate_ai_response(response)
        assert result.nutrient_deficiency == {"nitrogen": 0.3, "phosphorus": 0.1}