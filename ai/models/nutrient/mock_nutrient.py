"""
Deterministic Mock Nutrient Deficiency Detector for testing and fallback.
Simulates visual chlorosis, necrosis, and interveinal yellowing indicators for N, P, K, Fe, Mg, Zn.
"""

from pathlib import Path
from typing import List, Optional
from .base import BaseNutrientDetector
from ...inference.image_loader import ImageInput, ImageLoader
from ...schemas.nutrient import NutrientDeficiencyItem, NutrientDeficiencyResult, NutrientElement


class MockNutrientDetector(BaseNutrientDetector):
    """
    Mock nutrient detector providing deterministic responses and filename inspection.
    """

    DEFICIENCY_PRESETS = {
        "nitrogen": {
            "symptom": "General chlorosis (yellowing) starting on older lower leaves.",
            "zone": "older_leaves",
        },
        "phosphorus": {
            "symptom": "Dark green leaves developing reddish-purple pigmentation along margins.",
            "zone": "older_leaves",
        },
        "potassium": {
            "symptom": "Marginal leaf scorch (necrosis) and chlorosis on leaf tips.",
            "zone": "margins",
        },
        "iron": {
            "symptom": "Distinct interveinal chlorosis on young upper leaves, dark green veins.",
            "zone": "younger_leaves",
        },
        "magnesium": {
            "symptom": "Interveinal chlorosis on older leaves with green V-shape at base.",
            "zone": "interveinal",
        },
        "zinc": {
            "symptom": "Interveinal chlorosis, little-leaf clustering, and stunted internodes.",
            "zone": "younger_leaves",
        },
    }

    def detect(self, image: ImageInput) -> NutrientDeficiencyResult:
        """
        Execute mock nutrient detection.
        """
        _ = ImageLoader.load(image)

        has_def = False
        target_nutrient: Optional[NutrientElement] = None
        confidence = 0.90

        if isinstance(image, (str, Path)):
            fname = Path(image).name.lower()
            if "healthy" in fname or "clean" in fname or "no_nutrient" in fname:
                has_def = False
            elif "nitrogen" in fname or "n_def" in fname:
                has_def = True
                target_nutrient = "nitrogen"
            elif "phosphorus" in fname or "p_def" in fname:
                has_def = True
                target_nutrient = "phosphorus"
            elif "potassium" in fname or "k_def" in fname:
                has_def = True
                target_nutrient = "potassium"
            elif "iron" in fname or "fe_def" in fname:
                has_def = True
                target_nutrient = "iron"
            elif "magnesium" in fname or "mg_def" in fname:
                has_def = True
                target_nutrient = "magnesium"
            elif "zinc" in fname or "zn_def" in fname:
                has_def = True
                target_nutrient = "zinc"
            elif "low_conf" in fname:
                has_def = True
                target_nutrient = "nitrogen"
                confidence = 0.45

        if not has_def:
            return NutrientDeficiencyResult(
                has_deficiency=False,
                suspected_deficiencies=[],
                primary_deficiency=None,
                confidence=0.92,
            )

        nutrient_key = target_nutrient or "nitrogen"
        preset = self.DEFICIENCY_PRESETS[nutrient_key]

        item = NutrientDeficiencyItem(
            nutrient=nutrient_key,
            confidence=confidence,
            is_visual_indicator_only=True,
            symptom_description=preset["symptom"],
            affected_leaf_zone=preset["zone"],  # type: ignore
        )

        return NutrientDeficiencyResult(
            has_deficiency=True,
            suspected_deficiencies=[item],
            primary_deficiency=nutrient_key,
            confidence=confidence,
        )
