"""
Real Model Adapter for Disease Detection.
Provides standard interfaces for loading and running trained neural network weights
(e.g., PyTorch YOLOv8n-cls classification baseline).
Decouples framework details from downstream Pydantic contracts.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from ultralytics import YOLO

from .base import BaseDiseaseDetector
from .registry import CropDiseaseRegistry
from ...inference.image_loader import ImageInput, ImageLoader
from ...schemas.disease import BoundingBox, DiseaseDetectionBox, DiseaseDetectionResult

logger = logging.getLogger(__name__)


class DiseaseModelAdapter(BaseDiseaseDetector):
    """
    Adapter for executing trained vision models.
    Plugs trained PyTorch / YOLO weights directly into the SMART SPRAY pipeline.
    """

    def __init__(
        self,
        weights_path: Optional[Path | str] = None,
        architecture: str = "yolov8n-cls",
        registry: Optional[CropDiseaseRegistry] = None,
    ):
        super().__init__(registry=registry)
        self.architecture = architecture
        self.weights_path: Optional[Path] = Path(weights_path) if weights_path else None
        self._model: Optional[YOLO] = None
        self._is_loaded: bool = False

        if self.weights_path and self.weights_path.is_file():
            self.load_weights(self.weights_path)

    @property
    def is_loaded(self) -> bool:
        """Whether trained weights are currently loaded and ready for inference."""
        return self._is_loaded

    def load_weights(self, path: Path | str) -> None:
        """
        Load trained model weights from file.

        Args:
            path: Path to .pt or .onnx file.
        """
        weights_file = Path(path)
        if not weights_file.is_file():
            raise FileNotFoundError(f"Model weights file not found: {weights_file}")

        logger.info(f"Loading {self.architecture} weights from {weights_file}...")
        try:
            self._model = YOLO(str(weights_file))
            self.weights_path = weights_file
            self._is_loaded = True
            logger.info(f"Model weights loaded successfully from {weights_file}.")
        except Exception as e:
            self._is_loaded = False
            logger.error(f"Failed to load weights from {weights_file}: {e}")
            raise RuntimeError(f"Error loading model weights: {e}")

    def detect(self, image: ImageInput, crop: Optional[str] = None) -> DiseaseDetectionResult:
        """
        Execute real inference using trained YOLO baseline weights.
        """
        if not self._is_loaded or self._model is None:
            raise RuntimeError(
                f"Cannot run real model inference: No trained weights loaded for {self.architecture}. "
                "Train the model in Phase 2B, provide a valid weights_path, "
                "or use MockDiseaseDetector for local development."
            )

        # Preprocess input image into standard RGB PIL Image
        pil_img = ImageLoader.load(image)

        # Crop validation
        target_crop = (crop or "tomato").strip().lower()
        if target_crop == "corn":
            target_crop = "maize"

        if not self.registry.is_crop_supported(target_crop):
            return DiseaseDetectionResult(
                disease="unknown",
                confidence=0.20,
                crop=target_crop,
                is_healthy=False,
                confidence_level="low",
                requires_confirmation=True,
                symptoms=[f"Crop '{target_crop}' is not registered in the disease catalog."],
            )

        # Execute prediction using trained YOLO model
        results = self._model.predict(source=pil_img, verbose=False)
        top1_class_name = ""
        confidence = 0.0

        if results and len(results) > 0 and hasattr(results[0], "probs"):
            probs = results[0].probs
            top1_idx = int(probs.top1)
            confidence = float(probs.top1conf.item())
            names_dict = results[0].names
            raw_class = names_dict.get(top1_idx, "unknown")
            top1_class_name = str(raw_class).lower()

        # Parse trained class name format (e.g., "tomato_early_blight" -> crop="tomato", disease="early_blight")
        predicted_crop = target_crop
        predicted_disease = "unknown"

        if "_" in top1_class_name:
            parts = top1_class_name.split("_", 1)
            predicted_crop = parts[0]
            predicted_disease = parts[1]
        else:
            predicted_disease = top1_class_name

        # Align with target crop context if requested
        if target_crop and target_crop != predicted_crop and predicted_crop in self.registry.get_supported_crops():
            # If model predicts a different crop than requested context, adjust confidence / confirmation flag
            requires_conf = True
        else:
            requires_conf = self.settings.is_confirmation_required(confidence)

        is_healthy = (predicted_disease == "healthy")
        meta = self.registry.get_disease_metadata(predicted_crop, predicted_disease)
        display_name = meta["display_name"] if meta else predicted_disease.replace("_", " ").title()
        symptoms = [meta["symptoms"]] if meta and meta.get("symptoms") else [
            "Disease classification baseline (YOLOv8n-cls). Spatial localization/bounding boxes not provided by classification backbone."
        ]

        conf_level = self.settings.get_confidence_level(confidence)

        return DiseaseDetectionResult(
            disease=predicted_disease,
            display_name=display_name,
            confidence=round(confidence, 4),
            crop=predicted_crop,
            is_healthy=is_healthy,
            confidence_level=conf_level,
            requires_confirmation=requires_conf,
            detections=[],  # Classification baseline does not produce localized bboxes
            affected_area_percent=None,
            symptoms=symptoms,
        )
