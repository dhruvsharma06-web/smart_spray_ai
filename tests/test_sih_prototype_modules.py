"""
Unit test suite for SIH prototype modules:
- Nutrient Deficiency Detection
- Severity Estimation Engine
- Climate-Risk AI Engine
"""

import pytest
from PIL import Image

from ai.schemas.disease import DiseaseDetectionResult, BoundingBox
from ai.models.nutrient import MockNutrientDetector, get_nutrient_detector
from ai.schemas.pest import PestDetectionResult, DetectedPest
from ai.models.severity import CompositeSeverityEstimator, get_severity_estimator
from ai.risk import ClimateRiskEngine, get_climate_risk_engine
from ai.schemas.climate import AirSensorData, SensorTelemetry, SoilSensorData, WeatherForecastData
from ai.schemas.disease import BoundingBox
from ai.schemas.nutrient import NutrientDeficiencyResult
from ai.schemas.severity import SeverityAssessmentResult


def test_nutrient_detector_healthy(settings):
    """Verify healthy foliage returns no visual nutrient deficiencies."""
    detector = get_nutrient_detector()
    path = settings.SAMPLE_IMAGES_DIR / "sample_nutrient_healthy.jpg"

    result = detector.detect(path)
    assert isinstance(result, NutrientDeficiencyResult)
    assert result.has_deficiency is False
    assert result.primary_deficiency is None
    assert len(result.suspected_deficiencies) == 0


def test_nutrient_detector_nitrogen_deficiency(settings):
    """Verify visual nitrogen deficiency detection."""
    detector = get_nutrient_detector()
    path = settings.SAMPLE_IMAGES_DIR / "sample_nutrient_nitrogen.jpg"

    result = detector.detect(path)
    assert result.has_deficiency is True
    assert result.primary_deficiency == "nitrogen"
    assert len(result.suspected_deficiencies) == 1
    assert result.suspected_deficiencies[0].is_visual_indicator_only is True


def test_nutrient_detector_low_confidence(settings):
    """Verify low confidence nutrient detection enforces requires_confirmation = True."""
    detector = get_nutrient_detector()
    path = settings.SAMPLE_IMAGES_DIR / "sample_nutrient_low_conf.jpg"

    result = detector.detect(path)
    assert result.confidence < 0.60
    assert result.confidence_level == "low"
    assert result.requires_confirmation is True


def test_severity_estimator_healthy():
    """Verify severity engine returns healthy state when all diagnostic signals are clean."""
    estimator = get_severity_estimator()

    dis = DiseaseDetectionResult(disease="healthy", confidence=0.95, is_healthy=True)
    pest = PestDetectionResult(pests=[], total_count=0, infestation_severity="none")

    res = estimator.estimate(disease=dis, pest=pest)
    assert isinstance(res, SeverityAssessmentResult)
    assert res.level == "healthy"
    assert res.affected_area_percent == 0.0
    assert res.progression_risk == "low"


def test_severity_estimator_disease_stress():
    """Verify severity estimation from early blight disease input."""
    estimator = get_severity_estimator()

    dis = DiseaseDetectionResult(
        disease="early_blight",
        confidence=0.92,
        is_healthy=False,
        affected_area_percent=18.0,
    )

    res = estimator.estimate(disease=dis)
    assert res.level == "moderate"
    assert res.affected_area_percent == 18.0
    assert res.progression_risk == "medium"


def test_severity_estimator_severe_pest():
    """Verify severity estimation from severe pest infestation."""
    estimator = get_severity_estimator()

    pest = PestDetectionResult(
        pests=[
            DetectedPest(pest_type="whitefly", confidence=0.95, bounding_box=BoundingBox(ymin=0.1, xmin=0.1, ymax=0.3, xmax=0.3))
        ] * 12,
        dominant_pest="whitefly",
        infestation_severity="severe",
    )

    res = estimator.estimate(pest=pest)
    assert res.level == "critical"
    assert res.progression_risk == "rapid"


def test_climate_risk_drought_and_heat():
    """Verify drought and heat stress risk indices under dry hot conditions."""
    engine = get_climate_risk_engine()

    telemetry = SensorTelemetry(
        soil=SoilSensorData(moisture_percent=14.5, temperature_celsius=33.0),
        air=AirSensorData(temperature_celsius=38.5, humidity_percent=22.0, rainfall_mm=0.0),
        crop_stage="flowering",
    )

    risk = engine.evaluate_risk(telemetry, crop="tomato", crop_stage="flowering")
    assert risk.drought >= 0.70
    assert risk.heat >= 0.60
    assert len(risk.contributing_factors) > 0


def test_climate_risk_flood_and_waterlogging():
    """Verify flood and waterlogging risk indices under heavy rain and saturated soil."""
    engine = get_climate_risk_engine()

    telemetry = SensorTelemetry(
        soil=SoilSensorData(moisture_percent=92.0, temperature_celsius=21.0),
        air=AirSensorData(temperature_celsius=24.0, humidity_percent=90.0, rainfall_mm=35.0),
        weather=WeatherForecastData(upcoming_24h_rainfall_mm=65.0),
        crop_stage="vegetative",
    )

    risk = engine.evaluate_risk(telemetry, crop="potato")
    assert risk.flood >= 0.80
    assert risk.waterlogging >= 0.70
    assert len(risk.contributing_factors) > 0


def test_climate_risk_normal_conditions():
    """Verify low risk scores under optimal growing telemetry."""
    engine = get_climate_risk_engine()

    telemetry = SensorTelemetry(
        soil=SoilSensorData(moisture_percent=55.0, temperature_celsius=22.0),
        air=AirSensorData(temperature_celsius=25.0, humidity_percent=60.0, rainfall_mm=0.0),
    )

    risk = engine.evaluate_risk(telemetry)
    assert risk.drought < 0.20
    assert risk.heat < 0.20
    assert risk.flood == 0.0
    assert risk.waterlogging == 0.0
