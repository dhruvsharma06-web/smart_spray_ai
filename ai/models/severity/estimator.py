"""
Composite Severity Estimator Engine.
Evaluates multi-stressor diagnostic signals (disease, pest, nutrient)
to compute categorical severity level, affected leaf area %, and progression risk.
"""

from typing import Optional
from .base import BaseSeverityEstimator
from ...inference.image_loader import ImageInput
from ...schemas.disease import DiseaseDetectionResult
from ...schemas.nutrient import NutrientDeficiencyResult
from ...schemas.pest import PestDetectionResult
from ...schemas.severity import SeverityAssessmentResult, SeverityLevel


class CompositeSeverityEstimator(BaseSeverityEstimator):
    """
    Rule-based composite severity engine for field diagnostics.
    """

    SEVERITY_ORDER = {"healthy": 0, "low": 1, "moderate": 2, "high": 3, "critical": 4}
    ORDER_TO_LEVEL = {0: "healthy", 1: "low", 2: "moderate", 3: "high", 4: "critical"}

    def estimate(
        self,
        image: Optional[ImageInput] = None,
        disease: Optional[DiseaseDetectionResult] = None,
        pest: Optional[PestDetectionResult] = None,
        nutrient: Optional[NutrientDeficiencyResult] = None,
    ) -> SeverityAssessmentResult:
        """
        Calculate combined severity across all diagnostic models.
        """
        max_score = 0
        affected_area_estimates = []
        confidences = []

        # 1. Disease Severity Signal
        if disease:
            confidences.append(disease.confidence)
            if disease.is_healthy or disease.disease == "healthy":
                pass
            else:
                area = disease.affected_area_percent or 15.0
                affected_area_estimates.append(area)
                if area < 5.0:
                    max_score = max(max_score, 1)  # low
                elif area < 25.0:
                    max_score = max(max_score, 2)  # moderate
                elif area < 50.0:
                    max_score = max(max_score, 3)  # high
                else:
                    max_score = max(max_score, 4)  # critical

        # 2. Pest Severity Signal
        if pest:
            confidences.append(pest.confidence)
            p_sev = pest.infestation_severity
            if p_sev == "low":
                max_score = max(max_score, 1)
            elif p_sev == "moderate":
                max_score = max(max_score, 2)
            elif p_sev == "high":
                max_score = max(max_score, 3)
            elif p_sev == "severe":
                max_score = max(max_score, 4)

        # 3. Nutrient Deficiency Signal
        if nutrient:
            confidences.append(nutrient.confidence)
            if nutrient.has_deficiency:
                max_score = max(max_score, 2)  # moderate default for visual deficiency

        final_level: SeverityLevel = self.ORDER_TO_LEVEL[max_score]  # type: ignore
        avg_affected_area = (
            sum(affected_area_estimates) / len(affected_area_estimates)
            if affected_area_estimates
            else (0.0 if final_level == "healthy" else 15.0)
        )
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.90

        progression_risk = "medium"
        if final_level in ["high", "critical"]:
            progression_risk = "rapid"
        elif final_level == "healthy":
            progression_risk = "low"

        return SeverityAssessmentResult(
            level=final_level,
            affected_area_percent=round(avg_affected_area, 1),
            confidence=round(avg_conf, 2),
            progression_risk=progression_risk,  # type: ignore
        )
