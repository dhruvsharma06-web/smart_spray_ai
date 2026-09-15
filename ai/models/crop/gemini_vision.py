"""
Open-world plant and crop identification using multimodal Gemini models.
Provides general plant/crop identification from images without needing a closed-set YOLO model.
"""

import json
import logging
from typing import Optional
from google import genai
from google.genai import types
from google.genai.errors import APIError

from .base import BaseCropIdentifier
from ...config.settings import get_settings
from ...inference.image_loader import ImageInput, ImageLoader
from ...schemas.crop import AlternativeCropCandidate, CropIdentificationResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert botanical taxonomist and agricultural vision specialist for an AI farming assistant.
Your task is to identify the plant/crop species shown in the given image.

Guidelines:
1. Identify the common English name of the primary crop (e.g. "tomato", "maize", "potato", "wheat", "grape", "rice", "apple", "cotton").
2. Provide the botanical scientific name if recognized (e.g. "Solanum lycopersicum").
3. Estimate your identification confidence as a float between 0.0 and 1.0.
4. If the image is not a plant/crop, set is_plant=false, crop_name="unknown", and confidence < 0.5.
5. If the image is ambiguous, provide alternative candidates with their respective confidence scores.
6. Identify visible anatomical parts (leaves, stem, fruit, flower, roots).
7. Estimate the visual growth stage (seedling, vegetative, flowering, fruiting, maturation).
8. Provide brief botanical reasoning explaining morphological traits that led to this identification.
"""


class GeminiVisionCropIdentifier(BaseCropIdentifier):
    """
    Multimodal plant/crop identifier powered by Google Gemini (e.g., gemini-3.8-flash).
    Handles open-world recognition for any agricultural plant species.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        client: Optional[genai.Client] = None,
    ):
        self.settings = get_settings()
        self.model_name = model_name or self.settings.GEMINI_MODEL
        self.api_key = api_key or self.settings.GEMINI_API_KEY

        if client:
            self.client = client
        elif self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            # Client without explicit api_key attempts to use GEMINI_API_KEY environment variable
            self.client = genai.Client()

    def identify(self, image: ImageInput) -> CropIdentificationResult:
        """
        Identify the crop/plant species in the image using Gemini multimodal vision.

        Args:
            image: ImageInput (PIL Image, file path, bytes, or base64)

        Returns:
            CropIdentificationResult with structured classification and confidence metrics.
        """
        # Load and convert image to compressed JPEG bytes
        image_bytes = ImageLoader.to_bytes(image, format="JPEG", quality=85)

        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type="image/jpeg",
        )

        prompt = (
            "Analyze this agricultural image. Identify the crop/plant species, anatomical parts, "
            "growth stage, and provide your confidence score."
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[image_part, prompt],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=CropIdentificationResult,
                    temperature=0.1,
                ),
            )

            response_text = response.text
            if not response_text:
                raise ValueError("Empty response received from Gemini API.")

            data = json.loads(response_text)
            result = CropIdentificationResult.model_validate(data)

            # Re-enforce confidence rules and flags to ensure 100% compliance with settings
            conf = result.confidence
            conf_level = self.settings.get_confidence_level(conf)
            requires_confirmation = (
                self.settings.is_confirmation_required(conf)
                or not result.is_plant
                or (conf < 0.60)
            )

            # Return updated object with system-enforced confidence governance
            return result.model_copy(
                update={
                    "confidence_level": conf_level,
                    "requires_confirmation": requires_confirmation,
                }
            )

        except APIError as e:
            logger.error(f"Gemini API Error during crop identification: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to identify crop using Gemini Vision: {e}")
            raise
