"""
Deterministic Mock Disease Detector for testing and offline pipeline validation.
Simulates crop-aware diagnoses, healthy states, localized lesion bounding boxes,
and low-confidence safety overrides.
"""

from pathlib import Path
from typing import List, Optional
from .base import BaseDiseaseDetector
from .registry import CropDiseaseRegistry
from ...inference.image_loader import ImageInput, ImageLoader
from ...schemas.disease import BoundingBox, DiseaseDetectionBox, DiseaseDetectionResult


class MockDiseaseDetector(BaseDiseaseDetector):
    """
    Mock disease detector that produces predictable, deterministic responses.
    Allows testing downstream decisions without needing trained neural net weights.
    """

    def __init__(
        self,
        default_disease: str = "early_blight",
        default_confidence: float = 0.92,
        registry: Optional[CropDiseaseRegistry] = None,
    ):
        super().__init__(registry=registry)
        self.default_disease = default_disease
        self.default_confidence = default_confidence

    def detect(self, image: ImageInput, crop: Optional[str] = None) -> DiseaseDetectionResult:
        """
        Execute mock disease detection with crop-aware routing and filename inspection.
        """
        # Validate that the image can be loaded
        _ = ImageLoader.load(image)

        target_crop = (crop or "tomato").strip().lower()
        if target_crop == "corn":
            target_crop = "maize"

        # Check for unknown / unsupported crop
        if not self.registry.is_crop_supported(target_crop):
            return DiseaseDetectionResult(
                disease="unknown",
                display_name=f"Unknown Disease on Unsupported Crop ({target_crop})",
                confidence=0.30,
                crop=target_crop,
                is_healthy=False,
                confidence_level="low",
                requires_confirmation=True,
                symptoms=["Unregistered crop profile; visual symptoms cannot be reliably mapped."],
            )

        # Default disease and confidence for this crop
        disease = self.default_disease
        confidence = self.default_confidence
        is_healthy = False
        detections: List[DiseaseDetectionBox] = []

        # Check for filename hints if path provided
        if isinstance(image, (str, Path)):
            fname = Path(image).name.lower()
            if "healthy" in fname:
                disease = "healthy"
                is_healthy = True
                confidence = 0.94
            elif "late_blight" in fname:
                disease = "late_blight"
                confidence = 0.91
            elif "early_blight" in fname:
                disease = "early_blight"
                confidence = 0.93
            elif "low_conf" in fname or "ambiguous" in fname:
                confidence = 0.45
            elif "bacterial_spot" in fname:
                disease = "bacterial_spot"
                confidence = 0.88

        # If crop is potato and disease was early_blight default, let's keep or check validity
        if not self.registry.is_disease_valid_for_crop(target_crop, disease):
            # Fall back to first supported disease or healthy
            supported = self.registry.get_supported_diseases(target_crop)
            disease = supported[0] if supported else "healthy"

        if disease == "healthy":
            is_healthy = True
            affected_area = 0.0
        else:
            is_healthy = False
            affected_area = 15.0
            # Generate simulated lesion detection bounding boxes for localized disease
            detections = [
                DiseaseDetectionBox(
                    label=disease,
                    confidence=round(confidence - 0.02, 2),
                    bbox=BoundingBox(ymin=0.25, xmin=0.30, ymax=0.55, xmax=0.65),
                )
            ]

        meta = self.registry.get_disease_metadata(target_crop, disease)
        display_name = (
            meta["display_name"] if meta else disease.replace("_", " ").title()
        )
        symptoms = [meta["symptoms"]] if meta and meta.get("symptoms") else []

        conf_level = self.settings.get_confidence_level(confidence)
        requires_confirmation = self.settings.is_confirmation_required(confidence)

        return DiseaseDetectionResult(
            disease=disease,
            display_name=display_name,
            confidence=confidence,
            crop=target_crop,
            is_healthy=is_healthy,
            confidence_level=conf_level,
            requires_confirmation=requires_confirmation,
            detections=detections,
            affected_area_percent=affected_area,
            symptoms=symptoms,
        )
