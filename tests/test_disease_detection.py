"""
Comprehensive test suite for Disease Detection subsystem.
Covers healthy states, known diseases, unknown crops, unsupported disease routing,
confidence governance, invalid images, adapters, and schema contracts.
"""

import pytest
from PIL import Image

from ai.models.disease import (
    BaseDiseaseDetector,
    CropDiseaseRegistry,
    DiseaseModelAdapter,
    MockDiseaseDetector,
    get_disease_detector,
    get_disease_registry,
)
from ai.schemas.disease import BoundingBox, DiseaseDetectionBox, DiseaseDetectionResult


def test_mock_detection_known_disease_tomato(mock_disease_detector, sample_tomato_early_blight_path):
    """Verify diagnosis of known disease (Tomato -> Early Blight) with localization."""
    result = mock_disease_detector.detect(sample_tomato_early_blight_path, crop="tomato")

    assert isinstance(result, DiseaseDetectionResult)
    assert result.disease == "early_blight"
    assert result.crop == "tomato"
    assert result.is_healthy is False
    assert result.confidence >= 0.85
    assert result.confidence_level == "high"
    assert result.requires_confirmation is False
    assert len(result.detections) > 0
    assert result.detections[0].label == "early_blight"
    assert result.affected_area_percent is not None and result.affected_area_percent > 0


def test_mock_detection_healthy_crop(mock_disease_detector, sample_tomato_healthy_path):
    """Verify healthy crop detection (Tomato -> Healthy)."""
    result = mock_disease_detector.detect(sample_tomato_healthy_path, crop="tomato")

    assert result.disease == "healthy"
    assert result.is_healthy is True
    assert result.confidence >= 0.85
    assert result.confidence_level == "high"
    assert result.requires_confirmation is False
    assert len(result.detections) == 0
    assert result.affected_area_percent == 0.0


def test_mock_detection_potato_disease(mock_disease_detector, sample_potato_late_blight_path):
    """Verify potato crop disease diagnosis (Potato -> Late Blight)."""
    result = mock_disease_detector.detect(sample_potato_late_blight_path, crop="potato")

    assert result.disease == "late_blight"
    assert result.crop == "potato"
    assert result.is_healthy is False
    assert result.confidence >= 0.85
    assert result.requires_confirmation is False


def test_mock_detection_unknown_crop(mock_disease_detector, sample_pil_image):
    """Verify handling of an unknown/unsupported crop."""
    result = mock_disease_detector.detect(sample_pil_image, crop="dragonfruit")

    assert result.disease == "unknown"
    assert result.crop == "dragonfruit"
    assert result.confidence < 0.60
    assert result.confidence_level == "low"
    assert result.requires_confirmation is True


def test_mock_detection_low_confidence(mock_disease_detector, sample_disease_low_conf_path):
    """Verify low confidence detection enforces requires_confirmation = True."""
    result = mock_disease_detector.detect(sample_disease_low_conf_path, crop="tomato")

    assert result.confidence < 0.60
    assert result.confidence_level == "low"
    assert result.requires_confirmation is True


def test_invalid_image_input(mock_disease_detector):
    """Verify error on missing or invalid image input."""
    with pytest.raises(FileNotFoundError):
        mock_disease_detector.detect("non_existent_leaf_image_9999.jpg", crop="tomato")

    with pytest.raises(TypeError):
        mock_disease_detector.detect(12345, crop="tomato")  # type: ignore


def test_crop_aware_registry_lookups():
    """Verify crop-to-disease isolation and biological validity checks."""
    reg = get_disease_registry()

    # Supported crops
    assert reg.is_crop_supported("tomato") is True
    assert reg.is_crop_supported("potato") is True
    assert reg.is_crop_supported("maize") is True
    assert reg.is_crop_supported("corn") is True  # Alias check
    assert reg.is_crop_supported("unknown_crop_xyz") is False

    # Disease validity per crop
    assert reg.is_disease_valid_for_crop("tomato", "early_blight") is True
    assert reg.is_disease_valid_for_crop("potato", "late_blight") is True
    assert reg.is_disease_valid_for_crop("apple", "apple_scab") is True

    # Cross-crop rejection: Early Blight is not an apple disease in catalog
    assert reg.is_disease_valid_for_crop("apple", "early_blight") is False
    # Apple scab is not a tomato disease
    assert reg.is_disease_valid_for_crop("tomato", "apple_scab") is False


def test_crop_aware_registry_dynamic_registration():
    """Verify adding new crops and diseases dynamically without touching inference code."""
    reg = CropDiseaseRegistry()  # Fresh local instance
    assert reg.is_crop_supported("cotton") is False

    reg.register_crop_disease(
        crop="cotton",
        disease="bacterial_blight",
        display_name="Bacterial Blight",
        pathogen="Xanthomonas citri pv. malvacearum",
        symptoms="Angular water-soaked spots on leaves",
    )

    assert reg.is_crop_supported("cotton") is True
    assert reg.is_disease_valid_for_crop("cotton", "bacterial_blight") is True
    assert reg.get_display_name("cotton", "bacterial_blight") == "Bacterial Blight"


def test_disease_model_adapter_unloaded_behavior(sample_pil_image):
    """Verify real model adapter clearly refuses to predict without loaded weights."""
    adapter = DiseaseModelAdapter(weights_path=None)
    assert adapter.is_loaded is False

    with pytest.raises(RuntimeError) as exc_info:
        adapter.detect(sample_pil_image, crop="tomato")
    assert "No trained weights loaded" in str(exc_info.value)


def test_disease_detector_factory():
    """Verify factory returns appropriate detector backends."""
    # Explicit mock
    det_mock = get_disease_detector(mode="mock")
    assert isinstance(det_mock, MockDiseaseDetector)

    # Explicit real without weights (instantiates uninitialized adapter)
    det_real = get_disease_detector(mode="real")
    assert isinstance(det_real, DiseaseModelAdapter)
    assert det_real.is_loaded is False

    # Auto mode without weights defaults to mock
    det_auto = get_disease_detector(mode="auto")
    assert isinstance(det_auto, MockDiseaseDetector)


def test_disease_detection_result_schema_compatibility():
    """Verify schema backwards compatibility and property aliases."""
    # Test instantiating with 'disease'
    res1 = DiseaseDetectionResult(
        disease="early_blight",
        confidence=0.92,
        crop="tomato",
    )
    assert res1.name == "early_blight"
    assert res1.display_name == "Early Blight"
    assert res1.confidence_level == "high"
    assert res1.requires_confirmation is False

    # Test legacy instantiation with 'name'
    res2 = DiseaseDetectionResult.model_validate({
        "name": "healthy",
        "confidence": 0.88,
        "crop": "tomato",
    })
    assert res2.disease == "healthy"
    assert res2.is_healthy is True


def test_real_model_adapter_trained_inference(sample_tomato_early_blight_path, settings):
    """Test real model inference when trained best.pt weights exist."""
    weights_file = settings.ROOT_DIR / "ai" / "models" / "disease" / "weights" / "best.pt"
    if not weights_file.is_file():
        pytest.skip("Trained weights best.pt not found yet; skipping real inference test.")

    adapter = DiseaseModelAdapter(weights_path=weights_file)
    assert adapter.is_loaded is True

    result = adapter.detect(sample_tomato_early_blight_path, crop="tomato")
    assert isinstance(result, DiseaseDetectionResult)
    assert result.confidence > 0.0
    assert result.crop is not None
    assert result.confidence_level in ["high", "moderate", "low"]

