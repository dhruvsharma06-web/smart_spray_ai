"""
Pytest configuration and shared fixtures for SMART SPRAY AI tests.
"""

from pathlib import Path
import pytest
from PIL import Image

from ai.config.settings import get_settings
from ai.models.crop.mock_crop import MockCropIdentifier


@pytest.fixture
def settings():
    """Return test settings instance."""
    return get_settings()


@pytest.fixture
def mock_crop_identifier():
    """Return a fresh MockCropIdentifier instance."""
    return MockCropIdentifier()


@pytest.fixture
def sample_pil_image():
    """Return a simple in-memory green RGB PIL image."""
    return Image.new("RGB", (128, 128), color=(34, 139, 34))


@pytest.fixture
def sample_tomato_image_path(settings):
    """Path to generated sample tomato image."""
    path = settings.SAMPLE_IMAGES_DIR / "sample_tomato.jpg"
    assert path.exists(), f"Sample image missing at {path}"
    return path


@pytest.fixture
def sample_maize_image_path(settings):
    """Path to generated sample maize image."""
    path = settings.SAMPLE_IMAGES_DIR / "sample_maize.jpg"
    assert path.exists(), f"Sample image missing at {path}"
    return path


@pytest.fixture
def sample_low_conf_image_path(settings):
    """Path to low confidence test image."""
    path = settings.SAMPLE_IMAGES_DIR / "sample_low_conf_ambiguous.jpg"
    assert path.exists(), f"Sample image missing at {path}"
    return path


@pytest.fixture
def sample_not_plant_image_path(settings):
    """Path to non-plant test image."""
    path = settings.SAMPLE_IMAGES_DIR / "sample_not_a_plant.jpg"
    assert path.exists(), f"Sample image missing at {path}"
    return path


@pytest.fixture
def sample_tomato_early_blight_path(settings):
    """Path to sample tomato early blight image."""
    path = settings.SAMPLE_IMAGES_DIR / "sample_tomato_early_blight.jpg"
    assert path.exists(), f"Sample image missing at {path}"
    return path


@pytest.fixture
def sample_tomato_healthy_path(settings):
    """Path to sample tomato healthy image."""
    path = settings.SAMPLE_IMAGES_DIR / "sample_tomato_healthy.jpg"
    assert path.exists(), f"Sample image missing at {path}"
    return path


@pytest.fixture
def sample_potato_late_blight_path(settings):
    """Path to sample potato late blight image."""
    path = settings.SAMPLE_IMAGES_DIR / "sample_potato_late_blight.jpg"
    assert path.exists(), f"Sample image missing at {path}"
    return path


@pytest.fixture
def sample_disease_low_conf_path(settings):
    """Path to low confidence disease image."""
    path = settings.SAMPLE_IMAGES_DIR / "sample_disease_low_conf.jpg"
    assert path.exists(), f"Sample image missing at {path}"
    return path


@pytest.fixture
def mock_disease_detector():
    """Return a fresh MockDiseaseDetector instance."""
    from ai.models.disease.mock_disease import MockDiseaseDetector
    return MockDiseaseDetector()

