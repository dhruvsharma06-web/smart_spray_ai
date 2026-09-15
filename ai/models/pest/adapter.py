"""
Real Model Adapter for Pest Detection.
Loads and executes trained YOLO object detection or classification weights for agricultural pests.
"""

import logging
from pathlib import Path
from typing import Any, List, Optional
from ultralytics import YOLO

from .base import BasePestDetector
from ...inference.image_loader import ImageInput, ImageLoader
from ...schemas.disease import BoundingBox
from ...schemas.pest import DetectedPest, PestDetectionResult

logger = logging.getLogger(__name__)


class PestModelAdapter(BasePestDetector):
    """
    Adapter for executing trained YOLO pest detection models.
    Maps localized bounding boxes or classification scores directly into PestDetectionResult contracts.
    """

    def __init__(
        self,
        weights_path: Optional[Path | str] = None,
        architecture: str = "yolov8n-pest",
    ):
        super().__init__()
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
            raise FileNotFoundError(f"Pest model weights file not found: {weights_file}")

        logger.info(f"Loading {self.architecture} weights from {weights_file}...")
        try:
            self._model = YOLO(str(weights_file))
            self.weights_path = weights_file
            self._is_loaded = True
            logger.info(f"Pest model weights loaded successfully from {weights_file}.")
        except Exception as e:
            self._is_loaded = False
            logger.error(f"Failed to load pest weights from {weights_file}: {e}")
            raise RuntimeError(f"Error loading pest model weights: {e}")

    def detect(self, image: ImageInput) -> PestDetectionResult:
        """
        Execute pest detection using loaded YOLO weights.
        """
        if not self._is_loaded or self._model is None:
            raise RuntimeError(
                f"Cannot run real model inference: No trained weights loaded for {self.architecture}. "
                "Train the pest model in Phase 2C, provide a valid weights_path, "
                "or use MockPestDetector for local development."
            )

        pil_img = ImageLoader.load(image)
        width, height = pil_img.size

        # Execute prediction
        results = self._model.predict(source=pil_img, verbose=False)
        detected_pests: List[DetectedPest] = []
        overall_conf = 0.90

        if results and len(results) > 0:
            res = results[0]
            names_dict = getattr(res, "names", {})

            # 1. Bounding Box Object Detection Model
            if hasattr(res, "boxes") and res.boxes is not None and len(res.boxes) > 0:
                for box in res.boxes:
                    cls_id = int(box.cls[0].item())
                    confidence = float(box.conf[0].item())
                    pest_name = str(names_dict.get(cls_id, "pest")).lower()

                    # Get normalized xyxy coordinates
                    xyxy = box.xyxy[0].tolist()  # [xmin, ymin, xmax, ymax]
                    xmin_norm = round(max(0.0, min(1.0, xyxy[0] / width)), 4)
                    ymin_norm = round(max(0.0, min(1.0, xyxy[1] / height)), 4)
                    xmax_norm = round(max(0.0, min(1.0, xyxy[2] / width)), 4)
                    ymax_norm = round(max(0.0, min(1.0, xyxy[3] / height)), 4)

                    detected_pests.append(
                        DetectedPest(
                            pest_type=pest_name,
                            confidence=round(confidence, 4),
                            bounding_box=BoundingBox(
                                ymin=ymin_norm,
                                xmin=xmin_norm,
                                ymax=ymax_norm,
                                xmax=xmax_norm,
                            ),
                        )
                    )

            # 2. Classification Baseline Model (probs)
            elif hasattr(res, "probs") and res.probs is not None:
                probs = res.probs
                top1_idx = int(probs.top1)
                overall_conf = float(probs.top1conf.item())
                top1_name = str(names_dict.get(top1_idx, "clean_foliage")).lower()

                if top1_name != "clean_foliage" and top1_name != "none":
                    detected_pests.append(
                        DetectedPest(
                            pest_type=top1_name,
                            confidence=round(overall_conf, 4),
                            bounding_box=BoundingBox(ymin=0.20, xmin=0.20, ymax=0.50, xmax=0.50),
                        )
                    )

        return PestDetectionResult(pests=detected_pests, confidence=overall_conf)
