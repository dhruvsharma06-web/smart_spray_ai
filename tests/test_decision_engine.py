"""
Comprehensive Unit and Integration Tests for Person 3 Decision Engine.
Tests all rules, precedence levels, safety overrides, audit trails, demo scenarios, and API endpoints.
"""

import json
import pytest
from fastapi.testclient import TestClient

from ai.api import app
from ai.decision import (
    ActionType,
    DecisionEngine,
    DecisionResult,
    PriorityLevel,
    SafetyStatus,
    evaluate_decision,
)
from ai.schemas.pipeline import (
    ClimateRiskSummary,
    CropSummary,
    DiseaseSummary,
    FieldAnalysisOutput,
    SeveritySummary,
)

client = TestClient(app)


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture
def decision_engine() -> DecisionEngine:
    return DecisionEngine()


@pytest.fixture
def healthy_analysis_output() -> FieldAnalysisOutput:
    return FieldAnalysisOutput(
        crop=CropSummary(name="tomato", confidence=0.95),
        disease=DiseaseSummary(name="healthy", confidence=0.98),
        pests=[],
        nutrient_deficiency=None,
        severity=SeveritySummary(level="healthy", affected_area_percent=0.0),
        climate_risk=ClimateRiskSummary(drought=0.1, heat=0.1, flood=0.0, waterlogging=0.0),
        requires_confirmation=False,
        metadata={"knowledge_retrieval": {"found": False, "records": []}},
    )


@pytest.fixture
def early_blight_analysis_output() -> FieldAnalysisOutput:
    sample_treatment = {
        "product": "Mancozeb 75% WP (SAMPLE)",
        "active_ingredient": "Mancozeb",
        "formulation": "WP",
        "application_method": "Foliar spray",
        "label_rate": "2.5 g/L of water",
        "pre_harvest_interval_days": 7,
        "source": "SAMPLE — CIBRC Registration",
    }
    return FieldAnalysisOutput(
        crop=CropSummary(name="tomato", confidence=0.92),
        disease=DiseaseSummary(name="early_blight", confidence=0.88),
        pests=[],
        nutrient_deficiency=None,
        severity=SeveritySummary(level="high", affected_area_percent=35.0),
        climate_risk=ClimateRiskSummary(drought=0.2, heat=0.2, flood=0.0, waterlogging=0.0),
        requires_confirmation=False,
        metadata={
            "knowledge_retrieval": {
                "found": True,
                "records": [sample_treatment],
            }
        },
    )


# =====================================================================
# DEMO SCENARIO TESTS
# =====================================================================


class TestDemoScenarios:
    """Tests covering the five primary demonstration scenarios."""

    def test_scenario_1_spray_recommendation(
        self, decision_engine, early_blight_analysis_output
    ):
        """
        SCENARIO 1: Tomato early blight + high conf + verified treatment + suitable weather
        --> SPRAY (SAFE_TO_SPRAY)
        """
        sensors = {
            "soil": {"moisture_percent": 40.0, "temperature_celsius": 24.0},
            "air": {"temperature_celsius": 26.0, "humidity_percent": 55.0, "rainfall_mm": 0.0},
        }
        weather = {"upcoming_24h_rainfall_mm": 0.0}

        res = decision_engine.evaluate(
            field_analysis=early_blight_analysis_output,
            sensor_data=sensors,
            weather_data=weather,
        )

        assert isinstance(res, DecisionResult)
        assert res.action == ActionType.SPRAY
        assert res.safety_status == SafetyStatus.SAFE_TO_SPRAY
        assert res.priority in [PriorityLevel.HIGH, PriorityLevel.MEDIUM]
        assert res.requires_confirmation is False
        assert res.verified_treatment is not None
        assert "Mancozeb" in res.verified_treatment["product"]
        assert "RULE_RECOMMEND_SPRAY" in res.audit.triggered_rules

    def test_scenario_2_delay_recommendation(
        self, decision_engine, early_blight_analysis_output
    ):
        """
        SCENARIO 2: Tomato early blight + verified treatment + heavy rain forecast (25mm)
        --> DELAY (WEATHER_DELAY)
        """
        sensors = {
            "soil": {"moisture_percent": 45.0, "temperature_celsius": 22.0},
            "air": {"temperature_celsius": 25.0, "humidity_percent": 80.0, "rainfall_mm": 10.0},
        }
        weather = {"upcoming_24h_rainfall_mm": 25.0}  # > 15mm threshold

        res = decision_engine.evaluate(
            field_analysis=early_blight_analysis_output,
            sensor_data=sensors,
            weather_data=weather,
        )

        assert res.action == ActionType.DELAY
        assert res.safety_status == SafetyStatus.WEATHER_DELAY
        assert res.requires_confirmation is False
        assert res.verified_treatment is not None
        assert "DELAYED" in res.reason
        assert "RULE_SPRAY_DELAY_WEATHER" in res.audit.triggered_rules

    def test_scenario_3_no_action_healthy(
        self, decision_engine, healthy_analysis_output
    ):
        """
        SCENARIO 3: Healthy crop + normal soil moisture + normal climate
        --> NO_ACTION (FIELD_HEALTHY)
        """
        sensors = {
            "soil": {"moisture_percent": 45.0, "temperature_celsius": 24.0},
            "air": {"temperature_celsius": 25.0, "humidity_percent": 60.0, "rainfall_mm": 0.0},
        }

        res = decision_engine.evaluate(
            field_analysis=healthy_analysis_output,
            sensor_data=sensors,
        )

        assert res.action == ActionType.NO_ACTION
        assert res.safety_status == SafetyStatus.FIELD_HEALTHY
        assert res.priority == PriorityLevel.LOW
        assert res.requires_confirmation is False
        assert "RULE_NO_ACTION" in res.audit.triggered_rules

    def test_scenario_4_irrigate_recommendation(
        self, decision_engine, healthy_analysis_output
    ):
        """
        SCENARIO 4: Low soil moisture (15%) + drought risk (0.75) + safe conditions
        --> IRRIGATE (SAFE_TO_IRRIGATE)
        """
        sensors = {
            "soil": {"moisture_percent": 15.0, "temperature_celsius": 32.0},  # Low moisture
            "air": {"temperature_celsius": 36.0, "humidity_percent": 25.0, "rainfall_mm": 0.0},
        }
        healthy_analysis_output.climate_risk.drought = 0.75  # High drought risk

        res = decision_engine.evaluate(
            field_analysis=healthy_analysis_output,
            sensor_data=sensors,
        )

        assert res.action == ActionType.IRRIGATE
        assert res.safety_status == SafetyStatus.SAFE_TO_IRRIGATE
        assert res.priority == PriorityLevel.HIGH
        assert res.requires_confirmation is False
        assert res.duration_minutes is not None
        assert res.duration_minutes > 0
        assert "RULE_RECOMMEND_IRRIGATE" in res.audit.triggered_rules

    def test_scenario_5_low_confidence_warn(self, decision_engine):
        """
        SCENARIO 5: Low confidence AI diagnosis (45%) or requires_confirmation=True
        --> WARN (CONFIRMATION_REQUIRED)
        """
        low_conf_analysis = FieldAnalysisOutput(
            crop=CropSummary(name="unknown_plant", confidence=0.45),
            disease=DiseaseSummary(name="early_blight", confidence=0.45),
            pests=[],
            nutrient_deficiency=None,
            severity=SeveritySummary(level="moderate", affected_area_percent=20.0),
            climate_risk=ClimateRiskSummary(drought=0.1, heat=0.1, flood=0.0, waterlogging=0.0),
            requires_confirmation=True,
            metadata={"knowledge_retrieval": {"found": False, "records": []}},
        )

        res = decision_engine.evaluate(field_analysis=low_conf_analysis)

        assert res.action == ActionType.WARN
        assert res.safety_status == SafetyStatus.CONFIRMATION_REQUIRED
        assert res.priority == PriorityLevel.HIGH
        assert res.requires_confirmation is True
        assert "RULE_CONFIRMATION_REQUIRED" in res.audit.triggered_rules


# =====================================================================
# EDGE CASES & SAFETY LAYER TESTS
# =====================================================================


class TestSafetyAndEdgeCases:
    """Tests covering invalid telemetry, missing data, flood hazards, and missing treatments."""

    def test_invalid_telemetry_out_of_bounds(self, decision_engine, healthy_analysis_output):
        """Invalid telemetry (e.g. soil moisture 120%) triggers SAFETY_BLOCK / TELEMETRY_INVALID."""
        invalid_sensors = {
            "soil": {"moisture_percent": 120.0, "temperature_celsius": 25.0},
        }

        res = decision_engine.evaluate(
            field_analysis=healthy_analysis_output,
            sensor_data=invalid_sensors,
        )

        assert res.action == ActionType.WARN
        assert res.safety_status == SafetyStatus.TELEMETRY_INVALID
        assert res.priority == PriorityLevel.CRITICAL
        assert res.requires_confirmation is True
        assert "RULE_SAFETY_INVALID_TELEMETRY" in res.audit.triggered_rules

    def test_missing_verified_treatment_warn(self, decision_engine):
        """Disease detected but no verified treatment in RAG -> WARN (NO_VERIFIED_TREATMENT)."""
        no_treatment_analysis = FieldAnalysisOutput(
            crop=CropSummary(name="tomato", confidence=0.90),
            disease=DiseaseSummary(name="bacterial_spot", confidence=0.88),
            pests=[],
            nutrient_deficiency=None,
            severity=SeveritySummary(level="moderate", affected_area_percent=15.0),
            climate_risk=ClimateRiskSummary(drought=0.1, heat=0.1, flood=0.0, waterlogging=0.0),
            requires_confirmation=False,
            metadata={"knowledge_retrieval": {"found": False, "records": []}},  # No treatment
        )

        res = decision_engine.evaluate(field_analysis=no_treatment_analysis)

        assert res.action == ActionType.WARN
        assert res.safety_status == SafetyStatus.NO_VERIFIED_TREATMENT
        assert res.requires_confirmation is True
        assert "RULE_NO_VERIFIED_TREATMENT" in res.audit.triggered_rules

    def test_critical_climate_hazard_flood(self, decision_engine, healthy_analysis_output):
        """Flood risk >= 0.80 triggers critical CLIMATE_HAZARD override."""
        healthy_analysis_output.climate_risk.flood = 0.85

        res = decision_engine.evaluate(field_analysis=healthy_analysis_output)

        assert res.action == ActionType.WARN
        assert res.safety_status == SafetyStatus.CLIMATE_HAZARD
        assert res.priority == PriorityLevel.CRITICAL
        assert res.requires_confirmation is True
        assert "RULE_SAFETY_CRITICAL_CLIMATE_HAZARD" in res.audit.triggered_rules

    def test_contradictory_telemetry_check(self, decision_engine, healthy_analysis_output):
        """Soil moisture 95% but drought risk 0.85 triggers safety block."""
        sensors = {"soil": {"moisture_percent": 95.0, "temperature_celsius": 25.0}}
        healthy_analysis_output.climate_risk.drought = 0.85

        res = decision_engine.evaluate(
            field_analysis=healthy_analysis_output,
            sensor_data=sensors,
        )

        assert res.action == ActionType.WARN
        assert res.safety_status == SafetyStatus.SAFETY_BLOCK
        assert res.requires_confirmation is True
        assert "RULE_SAFETY_CONTRADICTORY_TELEMETRY" in res.audit.triggered_rules

    def test_missing_sensor_data_unmonitored_graceful(
        self, decision_engine, healthy_analysis_output
    ):
        """Engine handles missing sensor data gracefully using field analysis payload."""
        res = decision_engine.evaluate(
            field_analysis=healthy_analysis_output,
            sensor_data=None,
        )
        assert isinstance(res, DecisionResult)
        assert res.action == ActionType.NO_ACTION

    def test_irrigate_blocked_by_flood_risk(self, decision_engine, healthy_analysis_output):
        """Irrigation is blocked when flood risk is high (0.60), even if soil moisture is low (15%)."""
        sensors = {"soil": {"moisture_percent": 15.0, "temperature_celsius": 30.0}}
        healthy_analysis_output.climate_risk.flood = 0.60

        res = decision_engine.evaluate(
            field_analysis=healthy_analysis_output,
            sensor_data=sensors,
        )
        assert res.action != ActionType.IRRIGATE

    def test_irrigate_blocked_by_saturated_soil(self, decision_engine, healthy_analysis_output):
        """Irrigation is blocked when soil is saturated (85%), even if drought risk is flagged."""
        sensors = {"soil": {"moisture_percent": 85.0, "temperature_celsius": 30.0}}
        healthy_analysis_output.climate_risk.drought = 0.60

        res = decision_engine.evaluate(
            field_analysis=healthy_analysis_output,
            sensor_data=sensors,
        )
        assert res.action != ActionType.IRRIGATE

    def test_low_confidence_disease_does_not_spray_or_delay(
        self, decision_engine, early_blight_analysis_output
    ):
        """Low confidence disease detection (0.45) returns WARN, never SPRAY or DELAY."""
        early_blight_analysis_output.disease.confidence = 0.45
        early_blight_analysis_output.requires_confirmation = True

        res = decision_engine.evaluate(field_analysis=early_blight_analysis_output)
        assert res.action == ActionType.WARN
        assert res.action not in [ActionType.SPRAY, ActionType.DELAY]
        assert res.requires_confirmation is True

    def test_audit_trail_completeness(self, decision_engine, healthy_analysis_output):
        """Audit record contains triggered rules, inputs, and timestamp."""
        res = decision_engine.evaluate(field_analysis=healthy_analysis_output)
        assert res.audit is not None
        assert len(res.audit.triggered_rules) > 0
        assert "crop" in res.audit.inputs_considered
        assert res.audit.timestamp != ""


# =====================================================================
# FASTAPI ENDPOINT INTEGRATION TESTS
# =====================================================================


class TestDecisionAPIEndpoint:
    """Tests for POST /ai/decision endpoint."""

    def test_post_ai_decision_success(self, early_blight_analysis_output):
        payload = {
            "field_analysis": early_blight_analysis_output.model_dump(),
            "sensor_data": {
                "soil": {"moisture_percent": 40.0, "temperature_celsius": 24.0},
                "air": {"temperature_celsius": 26.0, "humidity_percent": 55.0},
            },
            "weather_data": {"upcoming_24h_rainfall_mm": 0.0},
            "crop_stage": "fruiting",
        }
        response = client.post("/ai/decision", json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["action"] == "SPRAY"
        assert data["safety_status"] == "SAFE_TO_SPRAY"
        assert "audit" in data
