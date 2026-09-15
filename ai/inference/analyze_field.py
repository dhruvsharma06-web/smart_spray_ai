"""
Unified Field Analysis Pipeline for SMART SPRAY AI Module.

Executes end-to-end diagnosis pipeline:
1. Crop identification
2. Disease detection
3. Pest detection
4. Nutrient deficiency detection
5. Severity estimation
6. Climate-risk assessment
7. Verified treatment retrieval
8. GenAI farmer explanation

Returns structured FieldAnalysisOutput matching Person 2's Decision Engine schema contract.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Union

from ..genai.explainer import ExplanationInput, get_genai_explainer
from .image_loader import ImageInput
from ..models.crop.mock_crop import MockCropIdentifier
from ..models.crop.gemini_vision import GeminiVisionCropIdentifier
from ..models.crop import get_crop_identifier
from ..models.disease import get_disease_detector
from ..models.nutrient import get_nutrient_detector
from ..models.pest import get_pest_detector
from ..models.severity import get_severity_estimator
from ..rag.knowledge_base import get_knowledge_base
from ..risk.climate_risk import get_climate_risk_engine
from ..schemas.climate import AirSensorData, SensorTelemetry, SoilSensorData, WeatherForecastData
from ..schemas.pipeline import (
    ClimateRiskSummary,
    CropSummary,
    DiseaseSummary,
    FieldAnalysisOutput,
    SeveritySummary,
)

logger = logging.getLogger(__name__)


def _build_sensor_telemetry(
    sensor_data: Optional[Union[SensorTelemetry, Dict[str, Any]]] = None,
    weather_data: Optional[Union[WeatherForecastData, Dict[str, Any]]] = None,
    crop_stage: str = "vegetative",
) -> SensorTelemetry:
    """Utility to construct valid SensorTelemetry from dicts or objects."""
    if isinstance(sensor_data, SensorTelemetry):
        return sensor_data

    # Parse soil and air if dict passed
    soil_obj = SoilSensorData(moisture_percent=45.0, temperature_celsius=24.0)
    air_obj = AirSensorData(temperature_celsius=28.0, humidity_percent=60.0, rainfall_mm=0.0)

    if isinstance(sensor_data, dict):
        if "soil" in sensor_data and isinstance(sensor_data["soil"], dict):
            soil_obj = SoilSensorData.model_validate(sensor_data["soil"])
        elif "moisture_percent" in sensor_data:
            soil_obj = SoilSensorData(
                moisture_percent=float(sensor_data.get("moisture_percent", 45.0)),
                temperature_celsius=float(sensor_data.get("soil_temp_c", 24.0)),
            )

        if "air" in sensor_data and isinstance(sensor_data["air"], dict):
            air_obj = AirSensorData.model_validate(sensor_data["air"])
        elif "humidity_percent" in sensor_data:
            air_obj = AirSensorData(
                temperature_celsius=float(sensor_data.get("temperature_celsius", 28.0)),
                humidity_percent=float(sensor_data.get("humidity_percent", 60.0)),
                rainfall_mm=float(sensor_data.get("rainfall_mm", 0.0)),
            )

    weather_obj: Optional[WeatherForecastData] = None
    if isinstance(weather_data, WeatherForecastData):
        weather_obj = weather_data
    elif isinstance(weather_data, dict):
        weather_obj = WeatherForecastData.model_validate(weather_data)

    return SensorTelemetry(
        soil=soil_obj,
        air=air_obj,
        weather=weather_obj,
        crop_stage=crop_stage,
    )


def analyze_field(
    image: ImageInput,
    sensor_data: Optional[Union[SensorTelemetry, Dict[str, Any]]] = None,
    weather_data: Optional[Union[WeatherForecastData, Dict[str, Any]]] = None,
    crop_stage: str = "vegetative",
    explainer_mode: str = "auto",
) -> FieldAnalysisOutput:
    """
    Unified entry point for AI diagnosis.

    Args:
        image: ImageInput (PIL Image, file path, bytes, or base64)
        sensor_data: SensorTelemetry or dictionary with IoT readings
        weather_data: WeatherForecastData or dictionary with forecast
        crop_stage: Growth stage (e.g. 'seedling', 'vegetative', 'flowering')
        explainer_mode: Mode for GenAI explainer ('auto', 'mock', 'gemini')

    Returns:
        FieldAnalysisOutput: Standard JSON contract for Person 2's Decision Engine
        along with GenAI explanation and treatment metadata.
    """

    # 1. Crop Identification
    crop_identifier = get_crop_identifier()
    crop_res = crop_identifier.identify(image)
    detected_crop = crop_res.crop_name

    # 2. Disease Detection (Crop-Aware)
    disease_detector = get_disease_detector()
    disease_res = disease_detector.detect(image, crop=detected_crop)

    # 3. Pest Detection
    pest_detector = get_pest_detector()
    pest_res = pest_detector.detect(image)

    # 4. Nutrient Deficiency Detection
    nutrient_detector = get_nutrient_detector()
    nutrient_res = nutrient_detector.detect(image)

    # 5. Severity Estimation
    severity_estimator = get_severity_estimator()
    severity_res = severity_estimator.estimate(
        image=image,
        disease=disease_res,
        pest=pest_res,
        nutrient=nutrient_res,
    )

    # 6. Climate-Risk Assessment
    telemetry = _build_sensor_telemetry(sensor_data, weather_data, crop_stage)
    climate_engine = get_climate_risk_engine()
    climate_res = climate_engine.evaluate_risk(telemetry=telemetry, crop=detected_crop, crop_stage=crop_stage)

    # 7. Verified Treatment Retrieval
    kb = get_knowledge_base()
    target_condition = (
        disease_res.disease
        if (disease_res and not disease_res.is_healthy and disease_res.disease != "healthy")
        else (pest_res.dominant_pest if (pest_res and pest_res.dominant_pest) else "healthy")
    )
    kb_res = kb.query(crop=detected_crop, disease_or_pest=target_condition)

    # 8. GenAI Farmer Explanation
    explainer = get_genai_explainer(mode=explainer_mode)
    exp_input = ExplanationInput(
        crop=crop_res,
        disease=disease_res,
        pest=pest_res,
        nutrient=nutrient_res,
        severity=severity_res,
        climate_risk=climate_res,
        treatments=kb_res.records,
        treatment_available=kb_res.found,
    )
    explanation_res = explainer.explain(exp_input)

    # Evaluate Global Confidence / Confirmation Governance
    requires_confirmation = any(
        [
            crop_res.requires_confirmation,
            disease_res.requires_confirmation,
            pest_res.requires_confirmation,
            nutrient_res.requires_confirmation,
            explanation_res.requires_confirmation,
        ]
    )

    # Assemble Output Schema Contract for Decision Engine
    crop_summary = CropSummary(name=crop_res.crop_name, confidence=crop_res.confidence)
    disease_summary = (
        DiseaseSummary(name=disease_res.disease, confidence=disease_res.confidence)
        if disease_res
        else None
    )
    severity_summary = (
        SeveritySummary(
            level=severity_res.level,
            affected_area_percent=severity_res.affected_area_percent,
        )
        if severity_res
        else None
    )
    climate_summary = ClimateRiskSummary(
        drought=climate_res.drought,
        heat=climate_res.heat,
        flood=climate_res.flood,
        waterlogging=climate_res.waterlogging,
    )

    nutrient_deficiency_str = (
        nutrient_res.primary_deficiency if (nutrient_res and nutrient_res.has_deficiency) else None
    )

    metadata = {
        "crop_details": crop_res.model_dump(),
        "disease_details": disease_res.model_dump(),
        "pest_details": pest_res.model_dump(),
        "nutrient_details": nutrient_res.model_dump(),
        "severity_details": severity_res.model_dump(),
        "climate_details": climate_res.model_dump(),
        "knowledge_retrieval": kb_res.to_dict(),
        "explanation": explanation_res.to_dict(),
    }

    return FieldAnalysisOutput(
        crop=crop_summary,
        disease=disease_summary,
        pests=pest_res.pests,
        nutrient_deficiency=nutrient_deficiency_str,
        severity=severity_summary,
        climate_risk=climate_summary,
        requires_confirmation=requires_confirmation,
        metadata=metadata,
    )
