"""
GenAI Explainer — Farmer-friendly explanation generator.

Takes structured AI analysis results and generates a plain-language explanation.
Supports both mock mode (offline/tests) and live Gemini mode.

STRICT SAFETY RULES:
  1. GenAI only EXPLAINS structured results — it never invents diagnoses.
  2. GenAI never invents pesticide names, dosage, or treatment instructions.
  3. GenAI never controls the pump or makes spray/no-spray decisions.
  4. If treatment data is unavailable, the explanation explicitly says so.
  5. Treatment information is passed through verbatim from the verified knowledge base.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..config.settings import get_settings
from ..schemas.crop import CropIdentificationResult
from ..schemas.climate import ClimateRiskResult
from ..schemas.disease import DiseaseDetectionResult
from ..schemas.nutrient import NutrientDeficiencyResult
from ..schemas.pest import PestDetectionResult
from ..schemas.severity import SeverityAssessmentResult
from ..schemas.treatment import VerifiedTreatmentRecord

logger = logging.getLogger(__name__)


# =====================================================================
# Data classes for input/output
# =====================================================================


@dataclass
class ExplanationInput:
    """
    Aggregated structured results to be explained.
    All fields are optional — the explainer adapts to whatever is available.
    """

    crop: Optional[CropIdentificationResult] = None
    disease: Optional[DiseaseDetectionResult] = None
    pest: Optional[PestDetectionResult] = None
    nutrient: Optional[NutrientDeficiencyResult] = None
    severity: Optional[SeverityAssessmentResult] = None
    climate_risk: Optional[ClimateRiskResult] = None
    treatments: List[VerifiedTreatmentRecord] = field(default_factory=list)
    treatment_available: bool = False


@dataclass
class ExplanationOutput:
    """
    Structured explanation response.

    Attributes:
        summary: Short farmer-friendly explanation text.
        sections: Labelled sections (what_detected, confidence, severity_risk,
                  why_it_matters, recommended_action, confirmation_warning).
        requires_confirmation: Whether the farmer needs to confirm before action.
        source: "mock" or "gemini" — identifies the explanation provider.
        disclaimer: Safety disclaimer always present.
    """

    summary: str
    sections: Dict[str, str]
    requires_confirmation: bool
    source: str
    disclaimer: str = (
        "This explanation is AI-generated based on structured analysis results. "
        "It does not replace professional agronomic advice. "
        "Treatment details come from the verified knowledge base only."
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "summary": self.summary,
            "sections": self.sections,
            "requires_confirmation": self.requires_confirmation,
            "source": self.source,
            "disclaimer": self.disclaimer,
        }


# =====================================================================
# Abstract base
# =====================================================================


class GenAIExplainer(ABC):
    """Base class for GenAI explanation generators."""

    @abstractmethod
    def explain(self, inputs: ExplanationInput) -> ExplanationOutput:
        """Generate a farmer-friendly explanation from structured results."""
        ...


# =====================================================================
# Mock explainer — works offline without any API key
# =====================================================================


class MockGenAIExplainer(GenAIExplainer):
    """
    Rule-based mock explainer that produces deterministic explanations
    from structured data. Used for tests and when no API key is available.
    """

    def explain(self, inputs: ExplanationInput) -> ExplanationOutput:
        sections: Dict[str, str] = {}
        needs_confirmation = False

        # 1. What was detected
        detected_parts: List[str] = []
        if inputs.crop:
            detected_parts.append(
                f"Crop identified: {inputs.crop.crop_name.title()} "
                f"(confidence: {inputs.crop.confidence:.0%})."
            )
            if inputs.crop.requires_confirmation:
                needs_confirmation = True
        if inputs.disease and not inputs.disease.is_healthy:
            detected_parts.append(
                f"Disease detected: {inputs.disease.display_name} "
                f"(confidence: {inputs.disease.confidence:.0%})."
            )
            if inputs.disease.requires_confirmation:
                needs_confirmation = True
        elif inputs.disease and inputs.disease.is_healthy:
            detected_parts.append("No disease detected — plant appears healthy.")
        if inputs.pest and inputs.pest.total_count > 0:
            detected_parts.append(
                f"Pest detected: {inputs.pest.dominant_pest} "
                f"({inputs.pest.total_count} instance(s), "
                f"severity: {inputs.pest.infestation_severity})."
            )
            if inputs.pest.requires_confirmation:
                needs_confirmation = True
        elif inputs.pest:
            detected_parts.append("No pests detected.")
        if inputs.nutrient and inputs.nutrient.has_deficiency:
            detected_parts.append(
                f"Nutrient deficiency suspected: {inputs.nutrient.primary_deficiency} "
                f"(visual indicator only — lab test recommended)."
            )
            if inputs.nutrient.requires_confirmation:
                needs_confirmation = True
        if not detected_parts:
            detected_parts.append("No analysis results available.")

        sections["what_detected"] = " ".join(detected_parts)

        # 2. Confidence
        confidences: List[str] = []
        if inputs.crop:
            confidences.append(
                f"Crop ID: {inputs.crop.confidence_level} ({inputs.crop.confidence:.0%})"
            )
        if inputs.disease:
            confidences.append(
                f"Disease: {inputs.disease.confidence_level} ({inputs.disease.confidence:.0%})"
            )
        if inputs.pest:
            confidences.append(
                f"Pest: {inputs.pest.confidence_level} ({inputs.pest.confidence:.0%})"
            )
        if inputs.nutrient:
            confidences.append(
                f"Nutrient: {inputs.nutrient.confidence_level} ({inputs.nutrient.confidence:.0%})"
            )
        sections["confidence"] = "; ".join(confidences) if confidences else "No confidence data."

        # 3. Severity / risk
        risk_parts: List[str] = []
        if inputs.severity:
            risk_parts.append(
                f"Overall severity: {inputs.severity.level}."
            )
            if inputs.severity.affected_area_percent is not None:
                risk_parts.append(
                    f"Affected area: {inputs.severity.affected_area_percent:.1f}%."
                )
        if inputs.climate_risk:
            high_risks = []
            if inputs.climate_risk.drought >= 0.5:
                high_risks.append(f"drought ({inputs.climate_risk.drought:.0%})")
            if inputs.climate_risk.heat >= 0.5:
                high_risks.append(f"heat stress ({inputs.climate_risk.heat:.0%})")
            if inputs.climate_risk.flood >= 0.5:
                high_risks.append(f"flood ({inputs.climate_risk.flood:.0%})")
            if inputs.climate_risk.waterlogging >= 0.5:
                high_risks.append(f"waterlogging ({inputs.climate_risk.waterlogging:.0%})")
            if high_risks:
                risk_parts.append(f"Climate risks: {', '.join(high_risks)}.")
            else:
                risk_parts.append("Climate risk: low.")
        sections["severity_risk"] = " ".join(risk_parts) if risk_parts else "No severity data."

        # 4. Why it matters
        why_parts: List[str] = []
        if inputs.disease and not inputs.disease.is_healthy:
            why_parts.append(
                f"{inputs.disease.display_name} can reduce crop yield and quality "
                f"if left untreated."
            )
        if inputs.pest and inputs.pest.total_count > 0:
            why_parts.append(
                f"{inputs.pest.dominant_pest.title() if inputs.pest.dominant_pest else 'Pest'} "
                f"infestation can cause direct feeding damage and transmit diseases."
            )
        if inputs.nutrient and inputs.nutrient.has_deficiency:
            why_parts.append(
                f"{inputs.nutrient.primary_deficiency.title() if inputs.nutrient.primary_deficiency else 'Nutrient'} "
                f"deficiency affects plant growth and photosynthesis."
            )
        if inputs.severity and inputs.severity.level in ("high", "critical"):
            why_parts.append(
                "High severity indicates urgent intervention is needed to prevent crop loss."
            )
        sections["why_it_matters"] = (
            " ".join(why_parts) if why_parts else "No immediate concerns detected."
        )

        # 5. Recommended next action
        actions: List[str] = []
        if inputs.treatment_available and inputs.treatments:
            # Relay verified treatment info — never invent
            for t in inputs.treatments:
                actions.append(
                    f"Verified option: {t.product} ({t.active_ingredient}), "
                    f"apply via {t.application_method} at {t.label_rate}. "
                    f"PHI: {t.pre_harvest_interval_days} days. "
                    f"Source: {t.source}."
                )
        elif inputs.disease and not inputs.disease.is_healthy:
            actions.append(
                "No verified treatment data available for this condition. "
                "Consult a local agricultural extension officer for recommendations."
            )
        if inputs.nutrient and inputs.nutrient.has_deficiency:
            actions.append(
                "Conduct a soil/tissue test to confirm the nutrient deficiency before fertilizer application."
            )
        if inputs.climate_risk:
            if inputs.climate_risk.drought >= 0.5:
                actions.append("Consider supplemental irrigation to mitigate drought stress.")
            if inputs.climate_risk.flood >= 0.5:
                actions.append("Ensure proper field drainage to prevent waterlogging.")
        if not actions:
            actions.append("Continue regular monitoring. No immediate action required.")
        sections["recommended_action"] = " ".join(actions)

        # 6. Confirmation warning
        if needs_confirmation:
            sections["confirmation_warning"] = (
                "⚠️ One or more AI assessments have low or moderate confidence. "
                "Please verify the results with an expert or on-ground inspection "
                "before taking action."
            )
        else:
            sections["confirmation_warning"] = ""

        # Build summary
        summary = self._build_summary(sections, needs_confirmation)

        return ExplanationOutput(
            summary=summary,
            sections=sections,
            requires_confirmation=needs_confirmation,
            source="mock",
        )

    @staticmethod
    def _build_summary(sections: Dict[str, str], needs_confirmation: bool) -> str:
        """Combine sections into a concise summary paragraph."""
        parts = [sections["what_detected"]]
        if sections.get("severity_risk") and sections["severity_risk"] != "No severity data.":
            parts.append(sections["severity_risk"])
        if sections.get("recommended_action"):
            parts.append(sections["recommended_action"])
        if needs_confirmation:
            parts.append(sections["confirmation_warning"])
        return " ".join(parts)


# =====================================================================
# Live Gemini explainer
# =====================================================================


class GeminiGenAIExplainer(GenAIExplainer):
    """
    Uses Google Gemini to generate farmer-friendly explanations
    from structured analysis results.

    SAFETY: The prompt strictly instructs the model to explain only the
    provided data and never invent treatments or dosages.
    """

    SYSTEM_PROMPT = """You are an agricultural AI assistant helping farmers understand crop analysis results.

STRICT RULES YOU MUST FOLLOW:
1. ONLY explain the structured data provided to you. Never invent diagnoses.
2. NEVER invent or suggest pesticide names, chemical names, dosages, concentrations, or application instructions.
3. If treatment records are provided, relay them exactly as given. Do not modify dosages or add new chemicals.
4. If no treatment data is provided, explicitly say "No verified treatment recommendation is available. Please consult a local agricultural extension officer."
5. NEVER make a spray/no-spray decision. You are explaining results, not controlling equipment.
6. Use simple, farmer-friendly language. Avoid technical jargon where possible.

OUTPUT FORMAT — Respond with a JSON object containing these keys:
- "what_detected": What the AI found in the image/sensors.
- "confidence": How confident the AI models are.
- "severity_risk": How serious the situation is.
- "why_it_matters": Why the farmer should care.
- "recommended_action": What the farmer should do next (using ONLY verified treatment data if provided).
- "confirmation_warning": Warning if confidence is low (empty string if confidence is adequate).
- "summary": A 2-3 sentence farmer-friendly summary combining the above.
"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.settings = get_settings()
        self.model_name = model_name or self.settings.GEMINI_MODEL
        self.api_key = api_key or self.settings.GEMINI_API_KEY

        from google import genai
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = genai.Client()

    def explain(self, inputs: ExplanationInput) -> ExplanationOutput:
        """Generate explanation using Gemini."""
        from google.genai import types

        data_payload = self._serialize_inputs(inputs)
        user_prompt = (
            "Based on the following structured crop analysis results, "
            "generate a farmer-friendly explanation.\n\n"
            f"```json\n{json.dumps(data_payload, indent=2)}\n```\n\n"
            "Remember: Only explain what is in the data. Do not invent "
            "treatments, pesticides, or dosages. If treatment_available is "
            "false, say no verified recommendation is available."
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[user_prompt],
                config=types.GenerateContentConfig(
                    system_instruction=self.SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )

            response_text = response.text
            if not response_text:
                logger.warning("Empty Gemini response — falling back to mock explainer.")
                return MockGenAIExplainer().explain(inputs)

            parsed = json.loads(response_text)

            # Determine if confirmation is needed from the inputs
            needs_confirmation = self._check_confirmation_needed(inputs)

            sections = {
                "what_detected": parsed.get("what_detected", ""),
                "confidence": parsed.get("confidence", ""),
                "severity_risk": parsed.get("severity_risk", ""),
                "why_it_matters": parsed.get("why_it_matters", ""),
                "recommended_action": parsed.get("recommended_action", ""),
                "confirmation_warning": parsed.get("confirmation_warning", ""),
            }

            return ExplanationOutput(
                summary=parsed.get("summary", sections["what_detected"]),
                sections=sections,
                requires_confirmation=needs_confirmation,
                source="gemini",
            )

        except Exception as e:
            logger.error(f"Gemini explanation failed: {e} — falling back to mock.")
            return MockGenAIExplainer().explain(inputs)

    @staticmethod
    def _serialize_inputs(inputs: ExplanationInput) -> Dict[str, Any]:
        """Convert ExplanationInput to a JSON-serializable dict for the prompt."""
        data: Dict[str, Any] = {}
        if inputs.crop:
            data["crop"] = {
                "name": inputs.crop.crop_name,
                "confidence": inputs.crop.confidence,
                "confidence_level": inputs.crop.confidence_level,
                "requires_confirmation": inputs.crop.requires_confirmation,
            }
        if inputs.disease:
            data["disease"] = {
                "name": inputs.disease.display_name,
                "is_healthy": inputs.disease.is_healthy,
                "confidence": inputs.disease.confidence,
                "confidence_level": inputs.disease.confidence_level,
                "requires_confirmation": inputs.disease.requires_confirmation,
            }
        if inputs.pest:
            data["pest"] = {
                "dominant_pest": inputs.pest.dominant_pest,
                "total_count": inputs.pest.total_count,
                "infestation_severity": inputs.pest.infestation_severity,
                "confidence": inputs.pest.confidence,
                "requires_confirmation": inputs.pest.requires_confirmation,
            }
        if inputs.nutrient:
            data["nutrient"] = {
                "has_deficiency": inputs.nutrient.has_deficiency,
                "primary_deficiency": inputs.nutrient.primary_deficiency,
                "confidence": inputs.nutrient.confidence,
                "requires_confirmation": inputs.nutrient.requires_confirmation,
            }
        if inputs.severity:
            data["severity"] = {
                "level": inputs.severity.level,
                "affected_area_percent": inputs.severity.affected_area_percent,
            }
        if inputs.climate_risk:
            data["climate_risk"] = {
                "drought": inputs.climate_risk.drought,
                "heat": inputs.climate_risk.heat,
                "flood": inputs.climate_risk.flood,
                "waterlogging": inputs.climate_risk.waterlogging,
            }
        data["treatment_available"] = inputs.treatment_available
        if inputs.treatments:
            data["treatments"] = [
                {
                    "product": t.product,
                    "active_ingredient": t.active_ingredient,
                    "application_method": t.application_method,
                    "label_rate": t.label_rate,
                    "pre_harvest_interval_days": t.pre_harvest_interval_days,
                    "safety_information": t.safety_information,
                    "source": t.source,
                }
                for t in inputs.treatments
            ]
        return data

    @staticmethod
    def _check_confirmation_needed(inputs: ExplanationInput) -> bool:
        """Check if any component requires confirmation."""
        if inputs.crop and inputs.crop.requires_confirmation:
            return True
        if inputs.disease and inputs.disease.requires_confirmation:
            return True
        if inputs.pest and inputs.pest.requires_confirmation:
            return True
        if inputs.nutrient and inputs.nutrient.requires_confirmation:
            return True
        return False


# =====================================================================
# Factory
# =====================================================================


def get_genai_explainer(mode: Optional[str] = None) -> GenAIExplainer:
    """
    Factory for GenAI explainers.

    Args:
        mode: "mock", "gemini", or "auto" (default).
              "auto" uses Gemini if an API key is configured, otherwise mock.

    Returns:
        A GenAIExplainer instance.
    """
    settings = get_settings()
    effective_mode = mode or "auto"

    if effective_mode == "mock":
        return MockGenAIExplainer()
    elif effective_mode == "gemini":
        return GeminiGenAIExplainer()
    elif effective_mode == "auto":
        if settings.GEMINI_API_KEY:
            return GeminiGenAIExplainer()
        else:
            logger.info("No GEMINI_API_KEY found — using mock GenAI explainer.")
            return MockGenAIExplainer()
    else:
        raise ValueError(f"Unknown GenAI explainer mode: {effective_mode}")
