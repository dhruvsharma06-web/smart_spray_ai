"""
Deterministic Mock Pest Detector for testing and pipeline verification.
Simulates pest instance detections, bounding boxes, counts, and severity levels.
"""

from pathlib import Path
from typing import List, Optional
from .base import BasePestDetector
from ...inference.image_loader import ImageInput, ImageLoader
from ...schemas.disease import BoundingBox
from ...schemas.pest import DetectedPest, PestDetectionResult


class MockPestDetector(BasePestDetector):
    """
    Mock pest detector producing predictable, deterministic responses.
    Allows testing downstream decision engines without external model dependencies.
    """

    def __init__(
        self,
        default_pest: str = "aphid",
        default_count: int = 3,
        default_confidence: float = 0.91,
    ):
        super().__init__()
        self.default_pest = default_pest
        self.default_count = default_count
        self.default_confidence = default_confidence

    def detect(self, image: ImageInput) -> PestDetectionResult:
        """
        Execute mock pest detection with filename inspection and preset heuristics.
        """
        # Ensure image is valid
        _ = ImageLoader.load(image)

        pest_type = self.default_pest
        count = self.default_count
        confidence = self.default_confidence

        # Filename hints
        if isinstance(image, (str, Path)):
            fname = Path(image).name.lower()
            if "no_pest" in fname or "clean" in fname or "healthy" in fname:
                count = 0
            elif "caterpillar" in fname:
                pest_type = "caterpillar"
                count = 1
            elif "whitefly" in fname:
                pest_type = "whitefly"
                count = 4
            elif "beetle" in fname:
                pest_type = "beetle"
                count = 2
            elif "low_conf" in fname:
                confidence = 0.45

        detected_list: List[DetectedPest] = []
        if count > 0:
            for i in range(count):
                ymin = round(0.15 + (i * 0.12), 2)
                xmin = round(0.20 + (i * 0.15), 2)
                ymax = round(ymin + 0.15, 2)
                xmax = round(xmin + 0.15, 2)
                detected_list.append(
                    DetectedPest(
                        pest_type=pest_type,
                        confidence=round(max(0.10, confidence - (i * 0.03)), 2),
                        bounding_box=BoundingBox(
                            ymin=min(0.95, ymin),
                            xmin=min(0.95, xmin),
                            ymax=min(0.99, ymax),
                            xmax=min(0.99, xmax),
                        ),
                    )
                )

        return PestDetectionResult(
            pests=detected_list,
            confidence=confidence,
            dominant_pest=pest_type if count > 0 else None,
        )
