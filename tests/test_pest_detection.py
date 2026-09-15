"""
Comprehensive test suite for Pest Detection subsystem (Phase 2C).
Covers mock pest detections, clean foliage, counts, infestation severity,
governance rules, factory logic, and real model adapter inference.
"""

import pytest
from PIL import Image

from ai.models.pest import (
    BasePestDetector,
    MockPestDetector,
    PestModelAdapter,
    get_pest_detector,
)
from ai.schemas.pest import DetectedPest, PestDetectionResult


def test_mock_pest_detection_basic(sample_pil_image):
    """Verify default mock pest detection (3 aphids)."""
    detector = MockPestDetector()
    result = detector.detect(sample_pil_image)

    assert isinstance(result, PestDetectionResult)
    assert result.total_count == 3
    assert result.dominant_pest == "aphid"
    assert result.infestation_severity == "moderate"
    assert result.confidence >= 0.85
    assert result.requires_confirmation is False
    assert len(result.pests) == 3


def test_mock_pest_detection_clean_foliage(settings):
    """Verify detection when foliage is clean (0 pests)."""
    detector = MockPestDetector()
    clean_path = settings.SAMPLE_IMAGES_DIR / "sample_pest_clean.jpg"
    assert clean_path.exists()

    result = detector.detect(clean_path)
    assert result.total_count == 0
    assert result.dominant_pest is None
    assert result.infestation_severity == "none"
    assert len(result.pests) == 0


def test_mock_pest_detection_caterpillar(settings):
    """Verify detection of specific pest type (caterpillar)."""
    detector = MockPestDetector()
    cat_path = settings.SAMPLE_IMAGES_DIR / "sample_pest_caterpillar.jpg"
    assert cat_path.exists()

    result = detector.detect(cat_path)
    assert result.total_count == 1
    assert result.dominant_pest == "caterpillar"
    assert result.infestation_severity == "low"
    assert len(result.pests) == 1


def test_mock_pest_detection_low_confidence(settings):
    """Verify low confidence pest detection enforces requires_confirmation = True."""
    detector = MockPestDetector()
    low_path = settings.SAMPLE_IMAGES_DIR / "sample_pest_low_conf.jpg"
    assert low_path.exists()

    result = detector.detect(low_path)
    assert result.confidence < 0.60
    assert result.confidence_level == "low"
    assert result.requires_confirmation is True


def test_pest_detector_factory():
    """Verify factory returns correct pest detector instances."""
    det_mock = get_pest_detector(mode="mock")
    assert isinstance(det_mock, MockPestDetector)

    det_real = get_pest_detector(mode="real")
    assert isinstance(det_real, PestModelAdapter)
    assert det_real.is_loaded is False


def test_real_pest_adapter_unloaded_behavior(sample_pil_image):
    """Verify real adapter refuses to detect without loaded weights."""
    adapter = PestModelAdapter(weights_path=None)
    assert adapter.is_loaded is False

    with pytest.raises(RuntimeError) as exc_info:
        adapter.detect(sample_pil_image)
    assert "No trained weights loaded" in str(exc_info.value)


def test_real_pest_adapter_trained_inference(settings):
    """Verify real pest inference when trained best.pt weights exist."""
    weights_path = settings.ROOT_DIR / "ai" / "models" / "pest" / "weights" / "best.pt"
    if not weights_path.is_file():
        pytest.skip("Trained pest weights best.pt not found yet; skipping real inference test.")

    adapter = PestModelAdapter(weights_path=weights_path)
    assert adapter.is_loaded is True

    sample_path = settings.SAMPLE_IMAGES_DIR / "sample_pest_aphid.jpg"
    result = adapter.detect(sample_path)

    assert isinstance(result, PestDetectionResult)
    assert result.confidence > 0.0
    assert result.confidence_level in ["high", "moderate", "low"]
