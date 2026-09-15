"""
Knowledge Base — RAG-style retrieval layer for verified agricultural knowledge.

Wraps the TreatmentDatabase and provides a unified query interface.
Designed to be extended later with vector search, LLM-augmented retrieval,
or external database connectors.

SAFETY PRINCIPLE:
  This module strictly separates verified knowledge from model-generated text.
  It never fabricates pesticide names, dosages, or application instructions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Any, Dict, List, Optional

from ..treatment.database import TreatmentDatabase, get_treatment_database
from ..schemas.treatment import VerifiedTreatmentRecord


class KnowledgeSource(str, Enum):
    """Identifies the origin of a knowledge response."""

    VERIFIED_DATABASE = "verified_database"
    NO_DATA = "no_data"


@dataclass
class KnowledgeResponse:
    """
    Structured response from the knowledge base.

    Attributes:
        source: Where the knowledge came from.
        found: Whether any verified records were found.
        records: List of verified treatment records (may be empty).
        message: Human-readable summary or "no verified recommendation".
        disclaimer: Safety/provenance disclaimer always included.
        query: The original query parameters for traceability.
    """

    source: KnowledgeSource
    found: bool
    records: List[VerifiedTreatmentRecord]
    message: str
    disclaimer: str
    query: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dictionary for JSON output."""
        return {
            "source": self.source.value,
            "found": self.found,
            "records": [r.model_dump() for r in self.records],
            "message": self.message,
            "disclaimer": self.disclaimer,
            "query": self.query,
        }


class KnowledgeBase:
    """
    Unified retrieval interface for verified agricultural knowledge.

    Current implementation wraps TreatmentDatabase for direct lookup.
    Designed to be extended with:
      - Vector similarity search over knowledge documents
      - LLM-augmented retrieval (with verified-data grounding)
      - External API connectors (CIBRC, EPA, etc.)
    """

    def __init__(
        self,
        treatment_db: Optional[TreatmentDatabase] = None,
    ) -> None:
        self._treatment_db = treatment_db or get_treatment_database()

    def query(
        self,
        crop: str,
        disease_or_pest: str,
    ) -> KnowledgeResponse:
        """
        Query the knowledge base for treatment recommendations.

        Args:
            crop: Crop name (e.g. "tomato", "potato").
            disease_or_pest: Disease or pest identifier (e.g. "early_blight").

        Returns:
            KnowledgeResponse with verified records or a safe fallback message.
        """
        records = self._treatment_db.lookup(crop, disease_or_pest)
        query_params = {"crop": crop, "disease_or_pest": disease_or_pest}

        if records:
            return KnowledgeResponse(
                source=KnowledgeSource.VERIFIED_DATABASE,
                found=True,
                records=records,
                message=(
                    f"Found {len(records)} verified treatment(s) for "
                    f"{crop} / {disease_or_pest}."
                ),
                disclaimer=(
                    "SAMPLE/DEMO DATA ONLY — These records are for prototype "
                    "demonstration. Verify with local agricultural authorities "
                    "before any field application."
                ),
                query=query_params,
            )

        return KnowledgeResponse(
            source=KnowledgeSource.NO_DATA,
            found=False,
            records=[],
            message=TreatmentDatabase.NO_VERIFIED_RECOMMENDATION,
            disclaimer=(
                "No verified treatment record is available for this "
                "crop-disease/pest combination. Do NOT use unverified suggestions."
            ),
            query=query_params,
        )

    def list_available(self) -> List[Dict[str, str]]:
        """List all (crop, disease_or_pest) combinations with verified data."""
        return [
            {"crop": crop, "disease_or_pest": dp}
            for crop, dp in self._treatment_db.list_available_keys()
        ]

    @property
    def total_records(self) -> int:
        """Total number of verified records available."""
        return self._treatment_db.total_records


@lru_cache()
def get_knowledge_base() -> KnowledgeBase:
    """Return a singleton KnowledgeBase."""
    return KnowledgeBase()
