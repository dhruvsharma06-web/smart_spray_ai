"""
FastAPI Endpoints for Person-1 AI Pipeline and Person-3 Decision Engine.
Exposes:
- POST /ai/analyze: Field analysis pipeline
- POST /ai/decision: Decision Engine operational recommendation evaluation
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError

from .decision.engine import evaluate_decision
from .decision.schemas import DecisionResult
from .inference.analyze_field import analyze_field
from .schemas.pipeline import FieldAnalysisOutput

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SMART SPRAY AI & Decision Engine Microservice",
    description="Person 1 AI/ML Diagnostics + Person 3 Decision Engine for Smart Spray",
    version="0.2.0",
)

# Enable CORS for SIH prototype frontends / backend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DecisionEvaluationRequest(BaseModel):
    """Input payload for POST /ai/decision endpoint."""

    field_analysis: Dict[str, Any]
    sensor_data: Optional[Dict[str, Any]] = None
    weather_data: Optional[Dict[str, Any]] = None
    crop_stage: str = "vegetative"


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check() -> Dict[str, str]:
    """Health check status endpoint."""
    return {"status": "ok", "service": "smart_spray_ai"}


@app.post(
    "/ai/analyze",
    response_model=FieldAnalysisOutput,
    status_code=status.HTTP_200_OK,
    summary="Analyze crop image and telemetry",
)
async def analyze_field_endpoint(
    image: UploadFile = File(..., description="Image file of the plant/crop foliage"),
    sensor_data: Optional[str] = Form(
        default=None,
        description="JSON string containing soil and air sensor readings (e.g. {\"soil\": {\"moisture_percent\": 20.0, \"temperature_celsius\": 25.0}, \"air\": {\"temperature_celsius\": 30.0, \"humidity_percent\": 50.0}})",
    ),
    weather_data: Optional[str] = Form(
        default=None,
        description="JSON string containing weather forecast data",
    ),
    crop_stage: str = Form(default="vegetative", description="Crop growth stage"),
    explainer_mode: str = Form(default="auto", description="GenAI explainer mode ('auto', 'mock', 'gemini')"),
) -> FieldAnalysisOutput:
    """
    Exposes Person 1 AI pipeline.

    Accepts multipart form-data:
    - image file (JPEG, PNG, WEBP)
    - optional sensor_data JSON string
    - optional weather_data JSON string
    - optional crop_stage string
    - optional explainer_mode string
    """
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file content-type: {image.content_type}. Must be an image file.",
        )

    try:
        image_bytes = await image.read()
        if not image_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded image file is empty.",
            )
    except Exception as e:
        logger.error(f"Error reading uploaded image file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded image file: {str(e)}",
        )

    # Parse sensor_data JSON string if provided
    parsed_sensor_data: Optional[Dict[str, Any]] = None
    if sensor_data:
        try:
            parsed_sensor_data = json.loads(sensor_data)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid JSON format provided in 'sensor_data' form field.",
            )

    # Parse weather_data JSON string if provided
    parsed_weather_data: Optional[Dict[str, Any]] = None
    if weather_data:
        try:
            parsed_weather_data = json.loads(weather_data)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid JSON format provided in 'weather_data' form field.",
            )

    try:
        # Call underlying analyze_field pipeline
        result = analyze_field(
            image=image_bytes,
            sensor_data=parsed_sensor_data,
            weather_data=parsed_weather_data,
            crop_stage=crop_stage,
            explainer_mode=explainer_mode,
        )
        return result
    except ValidationError as e:
        logger.error(f"Validation error in analyze_field result: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Pipeline schema validation error: {e.errors()}",
        )
    except Exception as e:
        logger.error(f"Unhandled exception during field analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal AI processing error: {str(e)}",
        )


@app.post(
    "/ai/decision",
    response_model=DecisionResult,
    status_code=status.HTTP_200_OK,
    summary="Evaluate Person 3 Decision Engine operational recommendation",
)
def evaluate_decision_endpoint(payload: DecisionEvaluationRequest) -> DecisionResult:
    """
    Exposes Person 3 Decision Engine.

    Accepts JSON body:
    - field_analysis: Result payload from /ai/analyze or FieldAnalysisOutput
    - sensor_data: Optional IoT telemetry dictionary
    - weather_data: Optional weather forecast dictionary
    - crop_stage: Crop growth stage string
    """
    try:
        result = evaluate_decision(
            field_analysis=payload.field_analysis,
            sensor_data=payload.sensor_data,
            weather_data=payload.weather_data,
            crop_stage=payload.crop_stage,
        )
        return result
    except Exception as e:
        logger.error(f"Unhandled exception in Decision Engine evaluation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Decision Engine processing error: {str(e)}",
        )
