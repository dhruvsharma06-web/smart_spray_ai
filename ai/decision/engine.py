"""
Person 3 Decision Engine Facade.
Provides the main entry point to evaluate field analysis and environmental telemetry into safe operational recommendations.
"""

import logging
from typing import Any, Dict, Optional, Union

from ..schemas.pipeline import FieldAnalysisOutput
from ..schemas.climate import SensorTelemetry, WeatherForecastData
from .config import DecisionSettings, get_decision_settings
from .rules import RuleEvaluator
from .safety import SafetyChecker
from .schemas import DecisionResult

logger = logging.getLogger(__name__)


class DecisionEngine:
    """
    Person 3 Decision Engine.
    Converts AI field diagnosis and environmental telemetry into safe, deterministic action recommendations.
    """

    def __init__(self, settings: Optional[DecisionSettings] = None):
        self.settings = settings or get_decision_settings()
        self.safety_checker = SafetyChecker(settings=self.settings)
        self.rule_evaluator = RuleEvaluator(settings=self.settings)

    def evaluate(
        self,
        field_analysis: Union[FieldAnalysisOutput, Dict[str, Any]],
        sensor_data: Optional[Union[SensorTelemetry, Dict[str, Any]]] = None,
        weather_data: Optional[Union[WeatherForecastData, Dict[str, Any]]] = None,
        crop_stage: str = "vegetative",
    ) -> DecisionResult:
        """
        Evaluate field analysis and telemetry to produce a safe operational DecisionResult.

        Args:
            field_analysis: FieldAnalysisOutput Pydantic model or dictionary representation.
            sensor_data: Optional SensorTelemetry model or telemetry dictionary.
            weather_data: Optional WeatherForecastData model or weather forecast dictionary.
            crop_stage: Crop growth stage string.

        Returns:
            DecisionResult: Typed Pydantic model containing action, reason, priority, safety status, and audit.
        """
        # Convert field_analysis to dictionary if Pydantic model
        if isinstance(field_analysis, FieldAnalysisOutput):
            analysis_dict = field_analysis.model_dump()
        elif isinstance(field_analysis, dict):
            analysis_dict = field_analysis
        else:
            analysis_dict = {}

        # Convert sensor_data to dict if model
        if isinstance(sensor_data, SensorTelemetry):
            sensor_dict = sensor_data.model_dump()
        elif isinstance(sensor_data, dict):
            sensor_dict = sensor_data
        else:
            sensor_dict = None

        # Convert weather_data to dict if model
        if isinstance(weather_data, WeatherForecastData):
            weather_dict = weather_data.model_dump()
        elif isinstance(weather_data, dict):
            weather_dict = weather_data
        else:
            weather_dict = None

        # 1. Run Safety Layer override checks
        safety_override = self.safety_checker.evaluate_safety_override(
            field_analysis_dict=analysis_dict,
            sensor_data=sensor_dict,
            weather_data=weather_dict,
        )
        if safety_override is not None:
            logger.warning(f"Safety override triggered: {safety_override.reason}")
            return safety_override

        # 2. Evaluate precedence rules
        result = self.rule_evaluator.evaluate_rules(
            analysis_dict=analysis_dict,
            sensor_data=sensor_dict,
            weather_data=weather_dict,
            crop_stage=crop_stage,
        )
        logger.info(f"Decision evaluated: Action={result.action.value}, Priority={result.priority.value}")
        return result


# Singleton instance facade
_DEFAULT_ENGINE = DecisionEngine()


def evaluate_decision(
    field_analysis: Union[FieldAnalysisOutput, Dict[str, Any]],
    sensor_data: Optional[Union[SensorTelemetry, Dict[str, Any]]] = None,
    weather_data: Optional[Union[WeatherForecastData, Dict[str, Any]]] = None,
    crop_stage: str = "vegetative",
    engine: Optional[DecisionEngine] = None,
) -> DecisionResult:
    """
    Helper function to evaluate decision using default or provided DecisionEngine.
    """
    active_engine = engine or _DEFAULT_ENGINE
    return active_engine.evaluate(
        field_analysis=field_analysis,
        sensor_data=sensor_data,
        weather_data=weather_data,
        crop_stage=crop_stage,
    )
