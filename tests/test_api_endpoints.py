"""
API integration tests for POST /ai/analyze endpoint.
"""

import json
import pytest
from fastapi.testclient import TestClient

from ai.api import app

client = TestClient(app)


def test_health_check():
    """Test GET /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "smart_spray_ai"}


def test_analyze_endpoint_end_to_end(sample_tomato_early_blight_path):
    """
    Test POST /ai/analyze endpoint with image file upload and form parameters.
    """
    sensor_payload = {
        "soil": {"moisture_percent": 22.0, "temperature_celsius": 26.0},
        "air": {"temperature_celsius": 32.0, "humidity_percent": 45.0, "rainfall_mm": 0.0},
    }
    weather_payload = {"upcoming_24h_rainfall_mm": 5.0}

    with open(sample_tomato_early_blight_path, "rb") as img_file:
        files = {
            "image": ("tomato_leaf.jpg", img_file, "image/jpeg"),
        }
        data = {
            "sensor_data": json.dumps(sensor_payload),
            "weather_data": json.dumps(weather_payload),
            "crop_stage": "fruiting",
            "explainer_mode": "mock",
        }
        response = client.post("/ai/analyze", files=files, data=data)

    assert response.status_code == 200, response.text
    res_json = response.json()

    # Verify Response Contract
    assert "crop" in res_json
    assert res_json["crop"]["name"] == "tomato"
    assert "disease" in res_json
    assert res_json["disease"]["name"] == "early_blight"
    assert "severity" in res_json
    assert "climate_risk" in res_json
    assert "requires_confirmation" in res_json
    assert "metadata" in res_json
    assert "explanation" in res_json["metadata"]


def test_analyze_endpoint_invalid_file_type():
    """Test POST /ai/analyze rejects non-image upload."""
    files = {
        "image": ("test.txt", b"not an image", "text/plain"),
    }
    response = client.post("/ai/analyze", files=files)
    assert response.status_code == 400
    assert "Must be an image file" in response.json()["detail"]


def test_analyze_endpoint_invalid_json_sensor_data(sample_tomato_healthy_path):
    """Test POST /ai/analyze returns 422 on bad JSON string in sensor_data."""
    with open(sample_tomato_healthy_path, "rb") as img_file:
        files = {
            "image": ("tomato_leaf.jpg", img_file, "image/jpeg"),
        }
        data = {
            "sensor_data": "{invalid json}",
        }
        response = client.post("/ai/analyze", files=files, data=data)

    assert response.status_code == 422
    assert "Invalid JSON format" in response.json()["detail"]
