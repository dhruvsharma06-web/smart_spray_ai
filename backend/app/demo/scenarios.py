from typing import Any, Dict, Optional

DEMO_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "TOMATO_EARLY_BLIGHT": {
        "description": "Tomato crop with moderate Early Blight infection under clear weather conditions. Authorizes SPRAY.",
        "expected_primary_decision": "SPRAY",
        "expected_risk_level": "MEDIUM",
        "expected_actuation": "SPRAY",
        "analysis": {
            "crop": {"name": "Tomato", "confidence": 0.94},
            "disease": {
                "name": "Tomato Early Blight",
                "confidence": 0.91,
                "severity": "medium",
                "affected_area_percent": 18.0,
            },
            "pests": [],
            "nutrient_deficiency": None,
            "severity": {"level": "MEDIUM", "affected_area_percent": 18.0},
            "climate_risk": {"drought": 0.10, "heat": 0.15, "flood": 0.0, "waterlogging": 0.0},
            "requires_confirmation": False,
            "metadata": {
                "farmer_explanation": "Tomato foliage shows concentric dark lesions characteristic of Early Blight. Weather is calm and dry, ideal for precision fungicide application.",
                "treatment_recommendations": [
                    {
                        "product": "Copper Oxychloride / Mancozeb",
                        "dosage": "2.5 g/L",
                        "instructions": "Calibrate boom sprayer for fine droplet deposition on middle canopy.",
                    }
                ],
                "mode": "DEMO_SCENARIO",
            },
        },
        "sensor_data": {
            "soil": {"moisture_percent": 28.0, "temperature_celsius": 24.0},
            "air": {"temperature_celsius": 26.0, "humidity_percent": 60.0, "rainfall_mm": 0.0},
        },
        "weather_data": {
            "temperature": 26.0,
            "humidity": 60.0,
            "rainfall": 0.0,
            "rain_probability": 10.0,
        },
    },
    "DISEASE_HEAVY_RAIN": {
        "description": "Severe Early Blight detected, but heavy incoming rain forces chemical delay to avoid runoff. Inhibits SPRAY.",
        "expected_primary_decision": "DELAY_SPRAY",
        "expected_risk_level": "HIGH",
        "expected_actuation": None,
        "analysis": {
            "crop": {"name": "Tomato", "confidence": 0.92},
            "disease": {
                "name": "Tomato Early Blight",
                "confidence": 0.88,
                "severity": "high",
                "affected_area_percent": 25.0,
            },
            "pests": [],
            "nutrient_deficiency": None,
            "severity": {"level": "HIGH", "affected_area_percent": 25.0},
            "climate_risk": {"drought": 0.0, "heat": 0.10, "flood": 0.75, "waterlogging": 0.50},
            "requires_confirmation": False,
            "metadata": {
                "farmer_explanation": "Early Blight present, but heavy rain forecast within hours would wash chemicals into watershed. Delaying spray until storm passes.",
                "treatment_recommendations": [],
                "mode": "DEMO_SCENARIO",
            },
        },
        "sensor_data": {
            "soil": {"moisture_percent": 35.0, "temperature_celsius": 21.0},
            "air": {"temperature_celsius": 22.0, "humidity_percent": 90.0, "rainfall_mm": 12.0},
        },
        "weather_data": {
            "temperature": 22.0,
            "humidity": 90.0,
            "rainfall": 12.0,
            "rain_probability": 85.0,
        },
    },
    "HEALTHY": {
        "description": "Clean foliage with vigorous vegetative growth. Baseline continuous monitoring. No action required.",
        "expected_primary_decision": "MONITOR",
        "expected_risk_level": "LOW",
        "expected_actuation": None,
        "analysis": {
            "crop": {"name": "Tomato", "confidence": 0.96},
            "disease": {"name": "healthy", "confidence": 0.95, "is_healthy": True},
            "pests": [],
            "nutrient_deficiency": None,
            "severity": None,
            "climate_risk": {"drought": 0.08, "heat": 0.12, "flood": 0.0, "waterlogging": 0.0},
            "requires_confirmation": False,
            "metadata": {
                "farmer_explanation": "Vines and foliage are healthy with zero detectable pathogen pressure. No chemical or irrigation interventions needed.",
                "treatment_recommendations": [],
                "mode": "DEMO_SCENARIO",
            },
        },
        "sensor_data": {
            "soil": {"moisture_percent": 32.0, "temperature_celsius": 23.0},
            "air": {"temperature_celsius": 25.0, "humidity_percent": 55.0, "rainfall_mm": 0.0},
        },
        "weather_data": {
            "temperature": 25.0,
            "humidity": 55.0,
            "rainfall": 0.0,
            "rain_probability": 5.0,
        },
    },
    "LOW_MOISTURE_HEAT": {
        "description": "Depleted root-zone soil moisture and dry thermal stress. Authorizes IRRIGATION cycle.",
        "expected_primary_decision": "IRRIGATE",
        "expected_risk_level": "HIGH",
        "expected_actuation": "IRRIGATE",
        "analysis": {
            "crop": {"name": "Tomato", "confidence": 0.90},
            "disease": {"name": "healthy", "confidence": 0.90, "is_healthy": True},
            "pests": [],
            "nutrient_deficiency": None,
            "severity": None,
            "climate_risk": {"drought": 0.88, "heat": 0.82, "flood": 0.0, "waterlogging": 0.0},
            "requires_confirmation": False,
            "metadata": {
                "farmer_explanation": "Severe soil moisture depletion (14%) combined with ambient heat stress. Immediate drip irrigation cycle authorized.",
                "treatment_recommendations": [],
                "mode": "DEMO_SCENARIO",
            },
        },
        "sensor_data": {
            "soil": {"moisture_percent": 14.0, "temperature_celsius": 32.0},
            "air": {"temperature_celsius": 36.0, "humidity_percent": 30.0, "rainfall_mm": 0.0},
        },
        "weather_data": {
            "temperature": 36.0,
            "humidity": 30.0,
            "rainfall": 0.0,
            "rain_probability": 0.0,
        },
    },
    "LOW_CONFIDENCE": {
        "description": "Ambiguous image quality or low model confidence. Requires agronomist confirmation. Inhibits SPRAY.",
        "expected_primary_decision": "WARN",
        "expected_risk_level": "LOW",
        "expected_actuation": None,
        "analysis": {
            "crop": {"name": "Tomato", "confidence": 0.48},
            "disease": {"name": "healthy", "confidence": 0.42, "is_healthy": True},
            "pests": [],
            "nutrient_deficiency": "Suspected Micronutrient Deficiency",
            "severity": None,
            "climate_risk": {"drought": 0.10, "heat": 0.10, "flood": 0.0, "waterlogging": 0.0},
            "requires_confirmation": True,
            "metadata": {
                "farmer_explanation": "Diagnostic confidence is below safe operational threshold (48%). Automatic spraying blocked until manual farmer verification.",
                "treatment_recommendations": [],
                "mode": "DEMO_SCENARIO",
            },
        },
        "sensor_data": {
            "soil": {"moisture_percent": 28.0, "temperature_celsius": 24.0},
            "air": {"temperature_celsius": 26.0, "humidity_percent": 60.0, "rainfall_mm": 0.0},
        },
        "weather_data": {
            "temperature": 26.0,
            "humidity": 60.0,
            "rainfall": 0.0,
            "rain_probability": 10.0,
        },
    },
}

def get_demo_scenario(name: str) -> Optional[Dict[str, Any]]:
    normalized = name.strip().upper().replace("-", "_").replace(" ", "_")
    return DEMO_SCENARIOS.get(normalized)
