"""
Schema exports for SMART SPRAY AI module.
"""

from .crop import (
    CropIdentificationResult,
    AlternativeCropCandidate,
    ConfidenceTier,
    CropGrowthStage,
    PlantPart,
)
from .disease import DiseaseDetectionResult, DiseaseDetectionBox, BoundingBox
from .pest import PestDetectionResult, DetectedPest
from .nutrient import NutrientDeficiencyResult, NutrientDeficiencyItem, NutrientElement
from .severity import SeverityAssessmentResult, SeverityLevel
from .climate import (
    SoilSensorData,
    AirSensorData,
    DailyForecast,
    WeatherForecastData,
    SensorTelemetry,
    ClimateRiskResult,
)
from .treatment import VerifiedTreatmentRecord
from .pipeline import (
    FieldAnalysisInput,
    FieldAnalysisOutput,
    CropSummary,
    DiseaseSummary,
    SeveritySummary,
    ClimateRiskSummary,
)

__all__ = [
    "CropIdentificationResult",
    "AlternativeCropCandidate",
    "ConfidenceTier",
    "CropGrowthStage",
    "PlantPart",
    "DiseaseDetectionResult",
    "DiseaseDetectionBox",
    "BoundingBox",
    "PestDetectionResult",
    "DetectedPest",
    "NutrientDeficiencyResult",
    "NutrientDeficiencyItem",
    "NutrientElement",
    "SeverityAssessmentResult",
    "SeverityLevel",
    "SoilSensorData",
    "AirSensorData",
    "DailyForecast",
    "WeatherForecastData",
    "SensorTelemetry",
    "ClimateRiskResult",
    "VerifiedTreatmentRecord",
    "FieldAnalysisInput",
    "FieldAnalysisOutput",
    "CropSummary",
    "DiseaseSummary",
    "SeveritySummary",
    "ClimateRiskSummary",
]
