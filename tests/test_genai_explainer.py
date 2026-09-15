"""
Tests for the GenAI Explanation Module.
All tests use MockGenAIExplainer — no API key required.
"""

import pytest

from ai.schemas.crop import CropIdentificationResult
from ai.schemas.disease import DiseaseDetectionResult
from ai.schemas.pest import PestDetectionResult, DetectedPest
from ai.schemas.nutrient import NutrientDeficiencyResult, NutrientDeficiencyItem
from ai.schemas.severity import SeverityAssessmentResult
from ai.schemas.climate import ClimateRiskResult
from ai.schemas.treatment import VerifiedTreatmentRecord
from ai.genai.explainer import (
    ExplanationInput,
    ExplanationOutput,
    MockGenAIExplainer,
    get_genai_explainer,
)


# =====================================================================
# Fixtures — reusable structured analysis results
# =====================================================================


@pytest.fixture
def crop_tomato() -> CropIdentificationResult:
    return CropIdentificationResult(
        crop_name="tomato",
        confidence=0.92,
        confidence_level="high",
        requires_confirmation=False,
        is_plant=True,
    )


@pytest.fixture
def crop_low_confidence() -> CropIdentificationResult:
    return CropIdentificationResult(
        crop_name="unknown_plant",
        confidence=0.45,
        confidence_level="low",
        requires_confirmation=True,
        is_plant=True,
    )


@pytest.fixture
def disease_early_blight() -> DiseaseDetectionResult:
    return DiseaseDetectionResult(
        disease="early_blight",
        confidence=0.88,
        crop="tomato",
    )


@pytest.fixture
def disease_healthy() -> DiseaseDetectionResult:
    return DiseaseDetectionResult(
        disease="healthy",
        confidence=0.95,
        crop="tomato",
    )


@pytest.fixture
def disease_low_confidence() -> DiseaseDetectionResult:
    return DiseaseDetectionResult(
        disease="late_blight",
        confidence=0.45,
        crop="potato",
    )


@pytest.fixture
def pest_aphid() -> PestDetectionResult:
    return PestDetectionResult(
        pests=[
            DetectedPest(
                pest_type="aphid",
                confidence=0.85,
                bounding_box={"ymin": 0.1, "xmin": 0.2, "ymax": 0.5, "xmax": 0.6},
            ),
            DetectedPest(
                pest_type="aphid",
                confidence=0.80,
                bounding_box={"ymin": 0.3, "xmin": 0.4, "ymax": 0.7, "xmax": 0.8},
            ),
        ],
    )


@pytest.fixture
def pest_none() -> PestDetectionResult:
    return PestDetectionResult(pests=[])


@pytest.fixture
def nutrient_nitrogen() -> NutrientDeficiencyResult:
    return NutrientDeficiencyResult(
        suspected_deficiencies=[
            NutrientDeficiencyItem(
                nutrient="nitrogen",
                confidence=0.72,
                symptom_description="Generalized chlorosis on older leaves.",
                affected_leaf_zone="older_leaves",
            ),
        ],
    )


@pytest.fixture
def severity_high() -> SeverityAssessmentResult:
    return SeverityAssessmentResult(
        level="high",
        affected_area_percent=45.0,
        confidence=0.85,
    )


@pytest.fixture
def severity_healthy() -> SeverityAssessmentResult:
    return SeverityAssessmentResult(
        level="healthy",
        affected_area_percent=0.0,
        confidence=0.95,
    )


@pytest.fixture
def climate_drought() -> ClimateRiskResult:
    return ClimateRiskResult(
        drought=0.75,
        heat=0.60,
        flood=0.10,
        waterlogging=0.05,
    )


@pytest.fixture
def climate_low_risk() -> ClimateRiskResult:
    return ClimateRiskResult(
        drought=0.10,
        heat=0.15,
        flood=0.05,
        waterlogging=0.05,
    )


@pytest.fixture
def treatment_sample() -> VerifiedTreatmentRecord:
    return VerifiedTreatmentRecord(
        crop="tomato",
        target_pest_or_disease="early_blight",
        product="Mancozeb 75% WP (SAMPLE)",
        active_ingredient="Mancozeb",
        formulation="WP",
        application_method="Foliar spray",
        approved_crop="Tomato",
        approved_target="Early Blight (Alternaria solani)",
        label_rate="2.5 g/L of water",
        pre_harvest_interval_days=7,
        safety_information="SAMPLE DATA — Wear protective clothing.",
        source="SAMPLE — Based on CIBRC India (demo only)",
        verification_date="2024-01-15",
    )


@pytest.fixture
def explainer() -> MockGenAIExplainer:
    return MockGenAIExplainer()


# =====================================================================
# Factory Tests
# =====================================================================


class TestFactory:
    """Tests for get_genai_explainer factory."""

    def test_mock_mode(self):
        e = get_genai_explainer(mode="mock")
        assert isinstance(e, MockGenAIExplainer)

    def test_auto_mode_without_api_key(self, monkeypatch):
        """Auto mode falls back to mock without an API key."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        # Clear the cached settings so it picks up the env change
        from ai.config.settings import get_settings
        get_settings.cache_clear()
        try:
            e = get_genai_explainer(mode="auto")
            assert isinstance(e, MockGenAIExplainer)
        finally:
            get_settings.cache_clear()

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="Unknown GenAI explainer mode"):
            get_genai_explainer(mode="invalid_xyz")


# =====================================================================
# Mock Explainer — Full Scenario Tests
# =====================================================================


class TestMockExplainerFullScenario:
    """Full pipeline scenario with all inputs populated."""

    def test_full_disease_scenario(
        self,
        explainer,
        crop_tomato,
        disease_early_blight,
        pest_none,
        nutrient_nitrogen,
        severity_high,
        climate_drought,
        treatment_sample,
    ):
        inputs = ExplanationInput(
            crop=crop_tomato,
            disease=disease_early_blight,
            pest=pest_none,
            nutrient=nutrient_nitrogen,
            severity=severity_high,
            climate_risk=climate_drought,
            treatments=[treatment_sample],
            treatment_available=True,
        )
        result = explainer.explain(inputs)

        assert isinstance(result, ExplanationOutput)
        assert result.source == "mock"
        assert "Tomato" in result.sections["what_detected"]
        assert "Early Blight" in result.sections["what_detected"]
        assert "No pests" in result.sections["what_detected"]
        assert "nitrogen" in result.sections["what_detected"].lower()
        assert "high" in result.sections["severity_risk"].lower()
        assert "45.0%" in result.sections["severity_risk"]
        assert "drought" in result.sections["severity_risk"].lower()
        assert "Mancozeb" in result.sections["recommended_action"]
        assert "2.5 g/L" in result.sections["recommended_action"]
        assert result.disclaimer != ""

    def test_healthy_scenario(
        self,
        explainer,
        crop_tomato,
        disease_healthy,
        pest_none,
        severity_healthy,
        climate_low_risk,
    ):
        inputs = ExplanationInput(
            crop=crop_tomato,
            disease=disease_healthy,
            pest=pest_none,
            severity=severity_healthy,
            climate_risk=climate_low_risk,
        )
        result = explainer.explain(inputs)

        assert "healthy" in result.sections["what_detected"].lower()
        assert "No pests" in result.sections["what_detected"]
        assert result.requires_confirmation is False
        assert result.sections["confirmation_warning"] == ""

    def test_pest_scenario(
        self,
        explainer,
        crop_tomato,
        pest_aphid,
    ):
        inputs = ExplanationInput(
            crop=crop_tomato,
            pest=pest_aphid,
        )
        result = explainer.explain(inputs)

        assert "aphid" in result.sections["what_detected"].lower()
        assert "2" in result.sections["what_detected"]  # 2 instances
        assert "aphid" in result.sections["why_it_matters"].lower()


class TestMockExplainerEdgeCases:
    """Edge cases for the mock explainer."""

    def test_empty_inputs(self, explainer):
        """Empty inputs produce a valid but minimal explanation."""
        result = explainer.explain(ExplanationInput())
        assert isinstance(result, ExplanationOutput)
        assert "No analysis results" in result.sections["what_detected"]
        assert result.requires_confirmation is False

    def test_only_crop(self, explainer, crop_tomato):
        """Only crop provided — no disease/pest/treatment."""
        result = explainer.explain(ExplanationInput(crop=crop_tomato))
        assert "Tomato" in result.sections["what_detected"]
        assert "92%" in result.sections["confidence"]

    def test_low_confidence_triggers_confirmation(
        self, explainer, crop_low_confidence, disease_low_confidence
    ):
        """Low-confidence results trigger confirmation warning."""
        inputs = ExplanationInput(
            crop=crop_low_confidence,
            disease=disease_low_confidence,
        )
        result = explainer.explain(inputs)
        assert result.requires_confirmation is True
        assert "⚠️" in result.sections["confirmation_warning"]
        assert "verify" in result.sections["confirmation_warning"].lower()

    def test_no_treatment_available_message(
        self, explainer, crop_tomato, disease_early_blight
    ):
        """When disease is detected but no treatment data, says so explicitly."""
        inputs = ExplanationInput(
            crop=crop_tomato,
            disease=disease_early_blight,
            treatment_available=False,
            treatments=[],
        )
        result = explainer.explain(inputs)
        assert "no verified treatment" in result.sections["recommended_action"].lower()
        assert "consult" in result.sections["recommended_action"].lower()

    def test_treatment_relayed_verbatim(
        self, explainer, crop_tomato, disease_early_blight, treatment_sample
    ):
        """Verified treatment info is relayed, not invented."""
        inputs = ExplanationInput(
            crop=crop_tomato,
            disease=disease_early_blight,
            treatments=[treatment_sample],
            treatment_available=True,
        )
        result = explainer.explain(inputs)
        action = result.sections["recommended_action"]
        # Must contain the EXACT product, ingredient, rate from the record
        assert "Mancozeb 75% WP (SAMPLE)" in action
        assert "Mancozeb" in action
        assert "2.5 g/L of water" in action
        assert "7 days" in action

    def test_climate_risk_drought_action(self, explainer, climate_drought):
        """Drought risk triggers irrigation recommendation."""
        inputs = ExplanationInput(climate_risk=climate_drought)
        result = explainer.explain(inputs)
        assert "irrigation" in result.sections["recommended_action"].lower()

    def test_nutrient_deficiency_recommends_lab_test(
        self, explainer, nutrient_nitrogen
    ):
        """Nutrient deficiency recommends soil/tissue test."""
        inputs = ExplanationInput(nutrient=nutrient_nitrogen)
        result = explainer.explain(inputs)
        assert "soil" in result.sections["recommended_action"].lower()
        assert "test" in result.sections["recommended_action"].lower()


class TestExplanationOutputSerialization:
    """Tests for ExplanationOutput.to_dict()."""

    def test_to_dict_has_all_keys(self, explainer, crop_tomato):
        result = explainer.explain(ExplanationInput(crop=crop_tomato))
        d = result.to_dict()
        assert "summary" in d
        assert "sections" in d
        assert "requires_confirmation" in d
        assert "source" in d
        assert "disclaimer" in d
        assert isinstance(d["sections"], dict)

    def test_to_dict_sections_keys(self, explainer, crop_tomato, disease_early_blight):
        result = explainer.explain(
            ExplanationInput(crop=crop_tomato, disease=disease_early_blight)
        )
        expected_keys = {
            "what_detected",
            "confidence",
            "severity_risk",
            "why_it_matters",
            "recommended_action",
            "confirmation_warning",
        }
        assert set(result.sections.keys()) == expected_keys


class TestSafetyGuardrails:
    """Verify the mock explainer never invents data."""

    def test_never_invents_treatment_without_data(self, explainer, crop_tomato, disease_early_blight):
        """Without treatment_available, must not mention any product/dosage."""
        result = explainer.explain(
            ExplanationInput(
                crop=crop_tomato,
                disease=disease_early_blight,
                treatment_available=False,
            )
        )
        action = result.sections["recommended_action"].lower()
        # Must not contain specific chemical names that aren't in inputs
        assert "mancozeb" not in action
        assert "chlorothalonil" not in action
        assert "metalaxyl" not in action
        # Must say no verified treatment
        assert "no verified treatment" in action

    def test_disclaimer_always_present(self, explainer):
        """Every explanation has a safety disclaimer."""
        result = explainer.explain(ExplanationInput())
        assert result.disclaimer != ""
        assert "AI-generated" in result.disclaimer

    def test_never_mentions_spray_decision(self, explainer, crop_tomato, disease_early_blight, treatment_sample):
        """Explainer never makes a spray/no-spray decision."""
        result = explainer.explain(
            ExplanationInput(
                crop=crop_tomato,
                disease=disease_early_blight,
                treatments=[treatment_sample],
                treatment_available=True,
            )
        )
        summary_lower = result.summary.lower()
        # Should not contain decisive spray commands
        assert "spray now" not in summary_lower
        assert "activate pump" not in summary_lower
        assert "start spraying" not in summary_lower
