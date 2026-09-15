"""
Transparent Rule-Based Climate Risk Engine.
Consumes soil moisture, soil temperature, ambient weather telemetry, forecast, crop type,
and growth stage to calculate drought, heat, flood, and waterlogging risk indices [0.0 - 1.0].
"""

from typing import Any, Dict, List, Union
from ..schemas.climate import (
    AirSensorData,
    ClimateRiskResult,
    SensorTelemetry,
    SoilSensorData,
    WeatherForecastData,
)


class ClimateRiskEngine:
    """
    Transparent rule-based climate risk assessment engine.
    Computes risk indices and logs contributing environmental factors.
    """

    def evaluate_risk(
        self,
        telemetry: Union[SensorTelemetry, Dict[str, Any]],
        crop: str = "tomato",
        crop_stage: str = "vegetative",
    ) -> ClimateRiskResult:
        """
        Evaluate drought, heat, flood, and waterlogging risk indices [0.0 - 1.0].
        """
        if isinstance(telemetry, dict):
            telemetry = SensorTelemetry.model_validate(telemetry)

        soil = telemetry.soil
        air = telemetry.air
        weather = telemetry.weather
        stage = telemetry.crop_stage or crop_stage

        factors: List[str] = []

        # ----------------------------------------------------
        # 1. DROUGHT RISK CALCULATION
        # ----------------------------------------------------
        drought_score = 0.0
        # Soil moisture driver
        if soil.moisture_percent < 15.0:
            drought_score += 0.65
            factors.append(f"Critically low soil moisture ({soil.moisture_percent:.1f}%)")
        elif soil.moisture_percent < 25.0:
            drought_score += 0.40
            factors.append(f"Low soil moisture ({soil.moisture_percent:.1f}%)")
        elif soil.moisture_percent < 35.0:
            drought_score += 0.20

        # High temp + low humidity acceleration
        if air.temperature_celsius > 34.0 and air.humidity_percent < 35.0:
            drought_score += 0.20
            factors.append(f"High atmospheric vapor deficit ({air.temperature_celsius}°C, {air.humidity_percent}% RH)")

        # Zero forecast rain bonus
        upcoming_rain = weather.upcoming_24h_rainfall_mm if weather else air.rainfall_mm
        if upcoming_rain == 0.0 and drought_score > 0.3:
            drought_score += 0.15

        # Crop stage vulnerability (flowering/fruiting is sensitive to drought)
        if stage.lower() in ["flowering", "fruiting"] and drought_score > 0.2:
            drought_score += 0.10
            factors.append(f"Crop in moisture-sensitive stage ({stage})")

        drought_risk = min(1.0, max(0.0, round(drought_score, 2)))

        # ----------------------------------------------------
        # 2. HEAT-STRESS RISK CALCULATION
        # ----------------------------------------------------
        heat_score = 0.0
        if air.temperature_celsius >= 40.0:
            heat_score += 0.85
            factors.append(f"Extreme air temperature ({air.temperature_celsius}°C)")
        elif air.temperature_celsius >= 35.0:
            heat_score += 0.60
            factors.append(f"High air temperature ({air.temperature_celsius}°C)")
        elif air.temperature_celsius >= 30.0:
            heat_score += 0.25

        if soil.temperature_celsius >= 32.0:
            heat_score += 0.15
            factors.append(f"Elevated root-zone soil temperature ({soil.temperature_celsius}°C)")

        heat_risk = min(1.0, max(0.0, round(heat_score, 2)))

        # ----------------------------------------------------
        # 3. FLOOD RISK CALCULATION
        # ----------------------------------------------------
        flood_score = 0.0
        total_precip = upcoming_rain + air.rainfall_mm
        if total_precip >= 100.0:
            flood_score += 0.90
            factors.append(f"Heavy precipitation alert ({total_precip:.1f} mm)")
        elif total_precip >= 50.0:
            flood_score += 0.65
            factors.append(f"Significant expected rainfall ({total_precip:.1f} mm)")
        elif total_precip >= 25.0:
            flood_score += 0.30

        flood_risk = min(1.0, max(0.0, round(flood_score, 2)))

        # ----------------------------------------------------
        # 4. WATERLOGGING RISK CALCULATION
        # ----------------------------------------------------
        waterlog_score = 0.0
        if soil.moisture_percent >= 90.0:
            waterlog_score += 0.75
            factors.append(f"Near-saturation soil moisture ({soil.moisture_percent:.1f}%)")
        elif soil.moisture_percent >= 80.0:
            waterlog_score += 0.45
            factors.append(f"High soil moisture saturation ({soil.moisture_percent:.1f}%)")

        if upcoming_rain > 20.0 and soil.moisture_percent >= 75.0:
            waterlog_score += 0.20
            factors.append("Rainfall forecast on saturated soil layer")

        waterlogging_risk = min(1.0, max(0.0, round(waterlog_score, 2)))

        return ClimateRiskResult(
            drought=drought_risk,
            heat=heat_risk,
            flood=flood_risk,
            waterlogging=waterlogging_risk,
            contributing_factors=factors,
        )


_GLOBAL_RISK_ENGINE = ClimateRiskEngine()


def get_climate_risk_engine() -> ClimateRiskEngine:
    """Return singleton climate risk engine instance."""
    return _GLOBAL_RISK_ENGINE
