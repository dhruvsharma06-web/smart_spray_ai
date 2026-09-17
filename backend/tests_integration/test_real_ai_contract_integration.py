import pytest
import pytest_asyncio
import uuid
import json
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import ASGITransport, AsyncClient, TimeoutException, ConnectError, HTTPStatusError, Response
from pydantic import ValidationError

from app.main import app
from app.ai.client import AIService
from app.decision.client import DecisionService
from app.schemas.ai_response import (
    AnalysisResult,
    BoundingBox,
    CropOut,
    DiseaseOut,
    PestOut,
    SeverityOut,
    ClimateRiskOut,
    validate_ai_response,
)
from app.services.analysis import AnalysisOrchestrator
from app.database.session import SessionLocal
from app.models import AIAnalysis, DiseaseDetection, PestDetection, ClimateRisk, Decision, Device, Farm, Field, User
from app.auth.security import create_access_token


@pytest_asyncio.fixture
async def app_client():
    """Async in-process client for testing endpoints with mocks and error injection."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def direct_test_setup():
    """Create test user, farm, field, and device in database for direct orchestrator & endpoint testing."""
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"realai_{suffix}@test.com",
        password_hash="fakehash",
        full_name=f"Real AI Tester {suffix}",
    )
    db.add(user)
    db.flush()

    farm = Farm(owner_id=user.id, name=f"AI Farm {suffix}", location={"lat": 12.34, "lon": 56.78})
    db.add(farm)
    db.flush()

    field = Field(
        farm_id=farm.id,
        name=f"AI Field {suffix}",
        crop="tomato",
        growth_stage="flowering",
        area_hectares=2.5,
    )
    db.add(field)
    db.flush()

    device = Device(
        field_id=field.id,
        device_uid=f"esp32-realai-{suffix}",
        name=f"Device {suffix}",
        status="ONLINE",
        tank_level=85.0,
        pump_active=False,
    )
    db.add(device)
    db.commit()

    token = create_access_token(str(user.id))
    headers = {"Authorization": f"Bearer {token}"}

    yield {
        "user_id": user.id,
        "farm_id": farm.id,
        "field_id": field.id,
        "device_id": device.id,
        "device_uid": device.device_uid,
        "headers": headers,
    }
    db.close()


# ---------------------------------------------------------------------------
# 1. Real AI Contract Schema Validations
# ---------------------------------------------------------------------------
class TestRealAIContractValidation:
    """Strict schema tests matching the frozen Real AI contract."""

    def test_full_real_ai_contract_validates(self):
        """AI response conforming to real contract shape with all optional fields."""
        payload = {
            "crop": {
                "name": "tomato",
                "confidence": 0.96,
                "scientific_name": "Solanum lycopersicum",
                "confidence_level": "high",
            },
            "disease": {
                "name": "early_blight",
                "confidence": 0.94,
                "severity": "moderate",
                "affected_area_percent": 18.5,
                "display_name": "Early Blight",
                "is_healthy": False,
                "symptoms": ["concentric_rings", "target_spots"],
                "detections": [
                    {
                        "label": "early_blight",
                        "confidence": 0.92,
                        "bbox": {"ymin": 0.1, "xmin": 0.2, "ymax": 0.3, "xmax": 0.4},
                    }
                ],
            },
            "pests": [
                {
                    "pest_type": "aphid",
                    "confidence": 0.88,
                    "count": 5,
                    "bounding_box": {"ymin": 0.12, "xmin": 0.34, "ymax": 0.25, "xmax": 0.48},
                }
            ],
            "nutrient_deficiency": {"nitrogen": 0.25, "has_deficiency": True},
            "severity": {
                "level": "moderate",
                "affected_area_percent": 18.5,
                "confidence": 0.90,
                "progression_risk": "medium",
            },
            "climate_risk": {
                "drought": 0.20,
                "heat": 0.35,
                "flood": 0.05,
                "waterlogging": 0.10,
            },
            "requires_confirmation": False,
            "recommendations": [
                "Apply copper fungicide spray",
                "Ensure proper row spacing for aeration",
            ],
            "metadata": {"pipeline_latency_ms": 320},
        }

        result = validate_ai_response(payload)
        assert isinstance(result, AnalysisResult)
        assert result.crop.name == "tomato"
        assert result.crop.confidence == 0.96
        assert result.crop.scientific_name == "Solanum lycopersicum"
        assert result.disease.name == "early_blight"
        assert result.disease.affected_area_percent == 18.5
        assert len(result.pests) == 1
        # Test pest_type normalized to name
        assert result.pests[0].name == "aphid"
        assert result.pests[0].bounding_box.ymin == 0.12
        assert result.pests[0].bounding_box.xmax == 0.48
        assert result.climate_risk.drought == 0.20
        assert len(result.recommendations) == 2

    def test_minimal_real_ai_contract_validates(self):
        """Valid AI response with only minimal required fields (optional fields omitted)."""
        payload = {
            "crop": {"name": "maize", "confidence": 0.89},
            "climate_risk": {
                "drought": 0.1,
                "heat": 0.2,
                "flood": 0.0,
                "waterlogging": 0.0,
            },
        }
        result = validate_ai_response(payload)
        assert result.crop.name == "maize"
        assert result.crop.confidence == 0.89
        assert result.disease is None
        assert result.pests == []
        assert result.nutrient_deficiency is None
        assert result.severity is None
        assert result.requires_confirmation is False

    def test_alias_compatibility_for_disease_and_crop(self):
        """Supports 'crop_name' and 'disease' aliases from real AI pipelines."""
        payload = {
            "crop": {"crop_name": "potato", "confidence": 0.92},
            "disease": {"disease": "late_blight", "confidence": 0.88},
            "climate_risk": {"drought": 0.1, "heat": 0.1, "flood": 0.1, "waterlogging": 0.1},
        }
        result = validate_ai_response(payload)
        assert result.crop.name == "potato"
        assert result.disease.name == "late_blight"

    def test_nutrient_deficiency_as_string_allowed(self):
        """Supports nutrient_deficiency passed as string identifier."""
        payload = {
            "crop": {"name": "rice", "confidence": 0.95},
            "nutrient_deficiency": "nitrogen",
            "climate_risk": {"drought": 0.0, "heat": 0.1, "flood": 0.3, "waterlogging": 0.2},
        }
        result = validate_ai_response(payload)
        assert result.nutrient_deficiency == "nitrogen"

    def test_bounding_box_coordinates_strictly_bounded(self):
        """Coordinates outside 0.0-1.0 must fail validation."""
        # ymin > 1.0
        invalid_payload = {
            "crop": {"name": "tomato", "confidence": 0.9},
            "pests": [
                {"name": "aphid", "confidence": 0.8, "bounding_box": {"ymin": 1.5, "xmin": 0.1, "ymax": 0.8, "xmax": 0.9}}
            ],
            "climate_risk": {"drought": 0.1, "heat": 0.1, "flood": 0.1, "waterlogging": 0.1},
        }
        with pytest.raises(ValidationError):
            validate_ai_response(invalid_payload)

        # negative coordinate
        invalid_payload["pests"][0]["bounding_box"] = {"ymin": -0.1, "xmin": 0.1, "ymax": 0.8, "xmax": 0.9}
        with pytest.raises(ValidationError):
            validate_ai_response(invalid_payload)

    def test_pest_without_name_or_pest_type_rejected(self):
        """Pest missing both name and pest_type must fail validation."""
        payload = {
            "crop": {"name": "tomato", "confidence": 0.9},
            "pests": [{"confidence": 0.85, "count": 2}],
            "climate_risk": {"drought": 0.1, "heat": 0.1, "flood": 0.1, "waterlogging": 0.1},
        }
        with pytest.raises(ValidationError):
            validate_ai_response(payload)

    def test_crop_confidence_above_one_rejected(self):
        """Crop confidence > 1.0 must be safely rejected."""
        payload = {
            "crop": {"name": "tomato", "confidence": 1.05},
            "climate_risk": {"drought": 0.1, "heat": 0.1, "flood": 0.1, "waterlogging": 0.1},
        }
        with pytest.raises(ValidationError):
            validate_ai_response(payload)

    def test_missing_crop_rejected(self):
        """Missing crop field must fail validation without inventing defaults."""
        payload = {
            "climate_risk": {"drought": 0.1, "heat": 0.1, "flood": 0.1, "waterlogging": 0.1}
        }
        with pytest.raises(ValidationError):
            validate_ai_response(payload)

    def test_missing_climate_risk_field_rejected(self):
        """Missing climate risk component must fail validation."""
        payload = {
            "crop": {"name": "tomato", "confidence": 0.9},
            "climate_risk": {"drought": 0.1, "heat": 0.1, "flood": 0.1},  # missing waterlogging
        }
        with pytest.raises(ValidationError):
            validate_ai_response(payload)


# ---------------------------------------------------------------------------
# 2. Complete Analysis Persistence & Hand-off
# ---------------------------------------------------------------------------
class TestRealContractAnalysisPersistence:
    """Verifies complete analysis persistence and AI -> Decision handoff."""

    @pytest.mark.asyncio
    async def test_successful_real_contract_persistence_and_handoff(
        self, app_client, direct_test_setup
    ):
        """
        Verify that a real-contract AI response:
        1. Persists AIAnalysis, DiseaseDetection, PestDetection, ClimateRisk
        2. Passes validated analysis to Decision Engine
        3. Persists Decision with expires_at
        4. Returns structured JSON to the frontend
        """
        real_ai_output = {
            "crop": {
                "name": "tomato",
                "confidence": 0.97,
                "scientific_name": "Solanum lycopersicum",
            },
            "disease": {
                "name": "early_blight",
                "confidence": 0.93,
                "severity": "moderate",
                "affected_area_percent": 22.0,
            },
            "pests": [
                {
                    "pest_type": "whitefly",
                    "confidence": 0.89,
                    "count": 12,
                    "bounding_box": {"ymin": 0.1, "xmin": 0.2, "ymax": 0.3, "xmax": 0.4},
                }
            ],
            "nutrient_deficiency": "nitrogen",
            "severity": {"level": "moderate", "affected_area_percent": 22.0},
            "climate_risk": {
                "drought": 0.25,
                "heat": 0.40,
                "flood": 0.10,
                "waterlogging": 0.15,
            },
            "requires_confirmation": False,
            "recommendations": ["Apply targeted fungicide"],
        }

        handoff_payload = None

        async def mock_real_ai_analyze(*args, **kwargs):
            return real_ai_output

        async def mock_decision_decide(self_inst, payload):
            nonlocal handoff_payload
            handoff_payload = payload
            return {
                "primary_decision": "SPRAY",
                "risk_level": "MEDIUM",
                "actions": [{"type": "SPRAY", "priority": "MEDIUM"}],
                "warnings": ["Moderate disease detected"],
                "requires_confirmation": False,
            }

        with patch.object(AIService, "analyze", new=mock_real_ai_analyze):
            with patch.object(DecisionService, "decide", new=mock_decision_decide):
                files = {"image": ("crop.jpg", b"valid image binary", "image/jpeg")}
                data = {"field_id": str(direct_test_setup["field_id"])}
                response = await app_client.post(
                    "/api/analysis",
                    files=files,
                    data=data,
                    headers=direct_test_setup["headers"],
                )

        assert response.status_code == 200, response.text
        res_data = response.json()
        assert "analysis_id" in res_data
        assert res_data["analysis"]["crop"]["name"] == "tomato"
        assert res_data["decision"]["primary_decision"] == "SPRAY"

        # Verify AI -> Decision Engine handoff received validated analysis
        assert handoff_payload is not None
        assert handoff_payload["analysis"]["crop"]["name"] == "tomato"
        assert handoff_payload["field_id"] == direct_test_setup["field_id"]

        # Verify Database Persistence
        db = SessionLocal()
        analysis_record = db.query(AIAnalysis).filter_by(id=res_data["analysis_id"]).first()
        assert analysis_record is not None
        assert analysis_record.image_uri is not None
        assert analysis_record.crop["name"] == "tomato"

        disease_record = (
            db.query(DiseaseDetection).filter_by(analysis_id=analysis_record.id).first()
        )
        assert disease_record is not None
        assert disease_record.name == "early_blight"
        assert disease_record.affected_area_percent == 22.0

        pest_record = (
            db.query(PestDetection).filter_by(analysis_id=analysis_record.id).first()
        )
        assert pest_record is not None
        assert pest_record.name == "whitefly"
        assert pest_record.count == 12
        assert pest_record.detections is not None
        assert "bounding_box" in pest_record.detections

        climate_record = (
            db.query(ClimateRisk).filter_by(analysis_id=analysis_record.id).first()
        )
        assert climate_record is not None
        assert climate_record.drought == 0.25

        decision_record = (
            db.query(Decision).filter_by(analysis_id=analysis_record.id).first()
        )
        assert decision_record is not None
        assert decision_record.primary_decision == "SPRAY"
        assert decision_record.expires_at is not None
        db.close()


# ---------------------------------------------------------------------------
# 3. Failure Handling & Device Safety Boundary
# ---------------------------------------------------------------------------
class TestRealAIFailureHandling:
    """Tests ensuring no device action occurs when AI analysis fails."""

    @pytest.mark.asyncio
    async def test_ai_timeout_returns_502_and_prevents_actuator_action(
        self, app_client, direct_test_setup
    ):
        """AI timeout returns 502 and prevents subsequent device commands."""
        with patch.object(AIService, "analyze", side_effect=TimeoutException("AI timeout")):
            files = {"image": ("test.jpg", b"fake image", "image/jpeg")}
            data = {"field_id": str(direct_test_setup["field_id"])}
            r = await app_client.post(
                "/api/analysis",
                files=files,
                data=data,
                headers=direct_test_setup["headers"],
            )
            assert r.status_code == 502

        # Device action without a valid decision must be rejected
        spray_resp = await app_client.post(
            f"/api/devices/{direct_test_setup['device_id']}/spray",
            params={"decision_id": 99999},
            headers=direct_test_setup["headers"],
        )
        assert spray_resp.status_code in (400, 404, 422)

    @pytest.mark.asyncio
    async def test_ai_service_unavailable_returns_502(
        self, app_client, direct_test_setup
    ):
        """ConnectError from AI service returns 502 Bad Gateway."""
        with patch.object(AIService, "analyze", side_effect=ConnectError("Connection refused")):
            files = {"image": ("test.jpg", b"fake image", "image/jpeg")}
            data = {"field_id": str(direct_test_setup["field_id"])}
            r = await app_client.post(
                "/api/analysis",
                files=files,
                data=data,
                headers=direct_test_setup["headers"],
            )
            assert r.status_code == 502

    @pytest.mark.asyncio
    async def test_ai_http_4xx_returns_502(self, app_client, direct_test_setup):
        """AI HTTP 400 Bad Request error returns 502 to client."""
        mock_resp = MagicMock(spec=Response)
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request from AI model"
        error = HTTPStatusError("400 Bad Request", request=MagicMock(), response=mock_resp)

        with patch.object(AIService, "analyze", side_effect=error):
            files = {"image": ("test.jpg", b"fake image", "image/jpeg")}
            data = {"field_id": str(direct_test_setup["field_id"])}
            r = await app_client.post(
                "/api/analysis",
                files=files,
                data=data,
                headers=direct_test_setup["headers"],
            )
            assert r.status_code == 502

    @pytest.mark.asyncio
    async def test_ai_http_5xx_returns_502(self, app_client, direct_test_setup):
        """AI HTTP 500 Internal Server Error returns 502 to client."""
        mock_resp = MagicMock(spec=Response)
        mock_resp.status_code = 500
        mock_resp.text = "Internal Model Crash"
        error = HTTPStatusError("500 Server Error", request=MagicMock(), response=mock_resp)

        with patch.object(AIService, "analyze", side_effect=error):
            files = {"image": ("test.jpg", b"fake image", "image/jpeg")}
            data = {"field_id": str(direct_test_setup["field_id"])}
            r = await app_client.post(
                "/api/analysis",
                files=files,
                data=data,
                headers=direct_test_setup["headers"],
            )
            assert r.status_code == 502

    @pytest.mark.asyncio
    async def test_malformed_ai_response_rejected_with_502(
        self, app_client, direct_test_setup
    ):
        """Malformed AI response is rejected by Pydantic and returns 502."""
        with patch.object(
            AIService,
            "analyze",
            side_effect=ValueError("AI response validation failed: missing crop.name"),
        ):
            files = {"image": ("test.jpg", b"fake image", "image/jpeg")}
            data = {"field_id": str(direct_test_setup["field_id"])}
            r = await app_client.post(
                "/api/analysis",
                files=files,
                data=data,
                headers=direct_test_setup["headers"],
            )
            assert r.status_code == 502

    @pytest.mark.asyncio
    async def test_invalid_image_type_rejected_with_415(
        self, app_client, direct_test_setup
    ):
        """Non-image upload is rejected with 415 before reaching AI service."""
        ai_called = False

        async def mock_analyze(*args, **kwargs):
            nonlocal ai_called
            ai_called = True
            return {}

        with patch.object(AIService, "analyze", new=mock_analyze):
            files = {"image": ("test.txt", b"plain text", "text/plain")}
            data = {"field_id": str(direct_test_setup["field_id"])}
            r = await app_client.post(
                "/api/analysis",
                files=files,
                data=data,
                headers=direct_test_setup["headers"],
            )
            assert r.status_code == 415
            assert not ai_called, "AI service must not be called for non-image upload"

    @pytest.mark.asyncio
    async def test_decision_engine_not_called_when_ai_fails(
        self, app_client, direct_test_setup
    ):
        """Decision Engine must never be called if AI service analysis fails."""
        decision_called = False

        async def mock_decide(*args, **kwargs):
            nonlocal decision_called
            decision_called = True
            return {}

        with patch.object(AIService, "analyze", side_effect=TimeoutException("AI timeout")):
            with patch.object(DecisionService, "decide", new=mock_decide):
                files = {"image": ("test.jpg", b"fake image", "image/jpeg")}
                data = {"field_id": str(direct_test_setup["field_id"])}
                r = await app_client.post(
                    "/api/analysis",
                    files=files,
                    data=data,
                    headers=direct_test_setup["headers"],
                )
                assert r.status_code == 502
                assert not decision_called, "Decision Engine must not be bypassed or called when AI fails"

    @pytest.mark.asyncio
    async def test_valid_ai_response_with_optional_fields_missing(
        self, app_client, direct_test_setup
    ):
        """Valid AI response with optional fields omitted succeeds without inventing fields."""
        minimal_output = {
            "crop": {"name": "wheat", "confidence": 0.91},
            "climate_risk": {
                "drought": 0.1,
                "heat": 0.15,
                "flood": 0.05,
                "waterlogging": 0.05,
            },
        }

        async def mock_minimal_ai(*args, **kwargs):
            return minimal_output

        async def mock_decision(*args, **kwargs):
            return {
                "primary_decision": "MONITOR",
                "risk_level": "LOW",
                "actions": [],
                "warnings": [],
                "requires_confirmation": False,
            }

        with patch.object(AIService, "analyze", new=mock_minimal_ai):
            with patch.object(DecisionService, "decide", new=mock_decision):
                files = {"image": ("wheat.jpg", b"valid image data", "image/jpeg")}
                data = {"field_id": str(direct_test_setup["field_id"])}
                r = await app_client.post(
                    "/api/analysis",
                    files=files,
                    data=data,
                    headers=direct_test_setup["headers"],
                )
                assert r.status_code == 200
                res = r.json()
                assert res["analysis"]["crop"]["name"] == "wheat"
                assert res["analysis"].get("disease") is None
                assert res["analysis"].get("pests") in (None, [])
                assert res["decision"]["primary_decision"] == "MONITOR"

    @pytest.mark.asyncio
    async def test_ai_failure_rolls_back_db_completely(
        self, app_client, direct_test_setup
    ):
        """When AI analysis fails, no AIAnalysis or Decision is left in the database."""
        db = SessionLocal()
        field_id = direct_test_setup["field_id"]
        count_analyses_before = db.query(AIAnalysis).filter_by(field_id=field_id).count()
        count_decisions_before = db.query(Decision).filter_by(field_id=field_id).count()
        db.close()

        with patch.object(AIService, "analyze", side_effect=TimeoutException("Simulated Timeout")):
            files = {"image": ("test.jpg", b"fake image", "image/jpeg")}
            data = {"field_id": str(field_id)}
            r = await app_client.post(
                "/api/analysis",
                files=files,
                data=data,
                headers=direct_test_setup["headers"],
            )
            assert r.status_code == 502

        db = SessionLocal()
        count_analyses_after = db.query(AIAnalysis).filter_by(field_id=field_id).count()
        count_decisions_after = db.query(Decision).filter_by(field_id=field_id).count()
        db.close()

        assert count_analyses_after == count_analyses_before
        assert count_decisions_after == count_decisions_before

    @pytest.mark.asyncio
    async def test_mock_ai_service_compatibility(self):
        """Mock AI service responds with contract-compliant shape and passes schema validation."""
        service = AIService()
        try:
            result = await service.analyze(
                image_bytes=b"mock_image_bytes",
                filename="test_mock.jpg",
                sensor_data={"soil": {"moisture_percent": 45}},
                weather_data={"temperature": 25},
                crop_stage="vegetative",
            )
            assert isinstance(result, dict)
            assert "crop" in result
            assert result["crop"]["name"] == "tomato"
            assert result["crop"]["confidence"] == 0.96
            assert "climate_risk" in result

            validated = validate_ai_response(result)
            assert validated.crop.name == "tomato"
        finally:
            await service.close()
