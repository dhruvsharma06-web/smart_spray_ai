"""
GenAI Explanation Package.
Generates farmer-friendly explanations from structured AI analysis results.
"""

from .explainer import (
    ExplanationInput,
    ExplanationOutput,
    GenAIExplainer,
    MockGenAIExplainer,
    GeminiGenAIExplainer,
    get_genai_explainer,
)

__all__ = [
    "ExplanationInput",
    "ExplanationOutput",
    "GenAIExplainer",
    "MockGenAIExplainer",
    "GeminiGenAIExplainer",
    "get_genai_explainer",
]
