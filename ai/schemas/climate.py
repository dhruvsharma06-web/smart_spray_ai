"""
Pydantic schemas for Sensor Telemetry, Weather, and Climate Risk Assessment.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class SoilSensorData(BaseModel):
    """IoT soil probe readings."""

    moisture_percent: float = Field(..., ge=0.0, le=100.0, description="Volumetric water content percentage.")
    temperature_celsius: float = Field(..., description="Soil temperature in degrees Celsius.")


class AirSensorData(BaseModel):
    """Ambient environmental readings."""

    temperature_celsius: float = Field(..., description="Ambient air temperature in Celsius.")
    humidity_percent: float = Field(..., ge=0.0, le=100.0, description="Relative humidity percentage.")
    rainfall_mm: float = Field(default=0.0, ge=0.0, description="Precipitation accumulated in mm.")


class DailyForecast(BaseModel):
    """Single-day meteorological forecast."""

    day_offset: int = Field(..., ge=1, le=7)
    expected_temp_max_c: float
    expected_temp_min_c: float
    expected_rainfall_mm: float = Field(default=0.0, ge=0.0)
    expected_humidity_percent: float = Field(..., ge=0.0, le=100.0)


class WeatherForecastData(BaseModel):
    """Short-term weather forecast window."""

    forecast_days: List[DailyForecast] = Field(default_factory=list)
    upcoming_24h_rainfall_mm: float = Field(default=0.0, ge=0.0)
    max_heat_index_c: Optional[float] = None


class SensorTelemetry(BaseModel):
    """Aggregated sensor and environmental input payload."""

    soil: SoilSensorData
    air: AirSensorData
    weather: Optional[WeatherForecastData] = None
    crop_stage: str = Field(default="vegetative", description="Crop growth stage.")


class ClimateRiskResult(BaseModel):
    """Climate risk probability indices between 0.0 and 1.0."""

    drought: float = Field(..., ge=0.0, le=1.0, description="Risk index for drought stress.")
    heat: float = Field(..., ge=0.0, le=1.0, description="Risk index for heat stress.")
    flood: float = Field(..., ge=0.0, le=1.0, description="Risk index for sudden inundation/flooding.")
    waterlogging: float = Field(..., ge=0.0, le=1.0, description="Risk index for soil saturation/root asphyxiation.")
    contributing_factors: List[str] = Field(default_factory=list)
