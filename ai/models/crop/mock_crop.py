"""
Mock implementation of Crop Identifier for offline development and deterministic unit testing.
Allows simulating high, moderate, and low confidence predictions without external API dependencies.
"""

from typing import Optional
from pathlib import Path
from .base import BaseCropIdentifier
from ...config.settings import get_settings
from ...inference.image_loader import ImageInput, ImageLoader
from ...schemas.crop import AlternativeCropCandidate, CropIdentificationResult


class MockCropIdentifier(BaseCropIdentifier):
    """
    Deterministic mock crop identifier.
    Can be configured dynamically or infers based on file names / defaults.
    """

    def __init__(
        self,
        default_crop: str = "tomato",
        default_scientific: str = "Solanum lycopersicum",
        default_confidence: float = 0.95,
        default_growth_stage: str = "vegetative",
    ):
        self.default_crop = default_crop
        self.default_scientific = default_scientific
        self.default_confidence = default_confidence
        self.default_growth_stage = default_growth_stage
        self.settings = get_settings()

        # Preset catalogue for known test crops
        self.preset_crops = {
            "tomato": {"sci": "Solanum lycopersicum", "parts": ["leaves", "stem", "fruit"]},
            "maize": {"sci": "Zea mays", "parts": ["leaves", "stem"]},
            "corn": {"sci": "Zea mays", "parts": ["leaves", "stem"]},
            "potato": {"sci": "Solanum tuberosum", "parts": ["leaves", "stem"]},
            "wheat": {"sci": "Triticum aestivum", "parts": ["leaves", "stem"]},
            "grape": {"sci": "Vitis vinifera", "parts": ["leaves", "fruit"]},
            "rice": {"sci": "Oryza sativa", "parts": ["leaves", "stem"]},
            "cotton": {"sci": "Gossypium hirsutum", "parts": ["leaves", "flower"]},
            "apple": {"sci": "Malus domestica", "parts": ["leaves", "fruit"]},
        }

    def identify(
        self,
        image: ImageInput,
        override_crop: Optional[str] = None,
        override_confidence: Optional[float] = None,
        override_is_plant: Optional[bool] = None,
    ) -> CropIdentificationResult:
        """
        Produce a deterministic mock identification result.
        Inspects filename hints if available (e.g. 'tomato_early_blight.jpg').
        """
        # Ensure image is valid
        _ = ImageLoader.load(image)

        crop_name = override_crop or self.default_crop
        confidence = override_confidence if override_confidence is not None else self.default_confidence
        is_plant = override_is_plant if override_is_plant is not None else True

        # Check for filename hints if path is passed
        if isinstance(image, (str, Path)) and not override_crop:
            filename = Path(image).name.lower()
            for known in self.preset_crops:
                if known in filename:
                    crop_name = known
                    break
            if "low_conf" in filename or "ambiguous" in filename:
                confidence = 0.45
            elif "mod_conf" in filename:
                confidence = 0.75
            elif "not_a_plant" in filename:
                is_plant = False
                crop_name = "unknown"
                confidence = 0.10

        meta = self.preset_crops.get(
            crop_name,
            {"sci": self.default_scientific, "parts": ["leaves", "stem"]},
        )

        conf_level = self.settings.get_confidence_level(confidence)
        # Low confidence or non-plant requires confirmation
        requires_confirmation = self.settings.is_confirmation_required(confidence) or not is_plant

        alternatives = []
        if conf_level == "low":
            alternatives = [
                AlternativeCropCandidate(crop_name="bell_pepper", confidence=0.35),
                AlternativeCropCandidate(crop_name="eggplant", confidence=0.20),
            ]

        return CropIdentificationResult(
            crop_name=crop_name,
            scientific_name=meta["sci"] if is_plant else None,
            confidence=confidence,
            confidence_level=conf_level,
            requires_confirmation=requires_confirmation,
            detected_parts=meta["parts"] if is_plant else [],
            growth_stage_visual=self.default_growth_stage if is_plant else "unknown",  # type: ignore
            is_plant=is_plant,
            reasoning=(
                f"Visual mock identifier matched characteristic foliage features for {crop_name}."
                if is_plant
                else "Image does not appear to show agricultural vegetation."
            ),
            alternative_candidates=alternatives,
        )
