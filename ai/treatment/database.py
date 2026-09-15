"""
Treatment Database — Lightweight verified agricultural treatment store.

All records are clearly marked as SAMPLE/DEMO DATA.
In production, this would be backed by a regulatory-compliant database.

SAFETY PRINCIPLE:
  Never invent pesticide names, dosage, concentration, or application instructions.
  If verified information is unavailable, return "no verified recommendation".
"""

from __future__ import annotations

from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from ..schemas.treatment import VerifiedTreatmentRecord


# ---------------------------------------------------------------------------
# Sample treatment records
# IMPORTANT: These are SAMPLE/DEMO records for prototype demonstration only.
# They must NOT be used for actual agricultural decision-making.
# Real deployment requires integration with authoritative databases such as
# CIBRC (India), EPA (US), or university extension publications.
# ---------------------------------------------------------------------------

_SAMPLE_RECORDS: List[VerifiedTreatmentRecord] = [
    # ---- Tomato — Early Blight ----
    VerifiedTreatmentRecord(
        crop="tomato",
        target_pest_or_disease="early_blight",
        product="Mancozeb 75% WP (SAMPLE)",
        active_ingredient="Mancozeb",
        formulation="WP",
        application_method="Foliar spray",
        approved_crop="Tomato",
        approved_target="Early Blight (Alternaria solani)",
        label_rate="2.5 g/L of water",
        pre_harvest_interval_days=7,
        reentry_interval_hours=24,
        safety_information=(
            "SAMPLE DATA — Wear protective clothing, gloves, and mask during application. "
            "Avoid spray drift near water bodies. Toxic to fish."
        ),
        source="SAMPLE — Based on CIBRC India registrations (demo only)",
        verification_date="2024-01-15",
        is_organic_certified=False,
        contraindications=["Do not mix with alkaline pesticides"],
    ),
    VerifiedTreatmentRecord(
        crop="tomato",
        target_pest_or_disease="early_blight",
        product="Chlorothalonil 75% WP (SAMPLE)",
        active_ingredient="Chlorothalonil",
        formulation="WP",
        application_method="Foliar spray",
        approved_crop="Tomato",
        approved_target="Early Blight (Alternaria solani)",
        label_rate="2.0 g/L of water",
        pre_harvest_interval_days=7,
        reentry_interval_hours=24,
        safety_information=(
            "SAMPLE DATA — Use respiratory protection. Keep away from eyes and skin. "
            "Harmful if inhaled. Do not apply near flowering crops (toxic to bees)."
        ),
        source="SAMPLE — Based on US EPA label references (demo only)",
        verification_date="2024-01-15",
        is_organic_certified=False,
        contraindications=["Do not mix with EC formulations"],
    ),
    # ---- Tomato — Late Blight ----
    VerifiedTreatmentRecord(
        crop="tomato",
        target_pest_or_disease="late_blight",
        product="Metalaxyl 8% + Mancozeb 64% WP (SAMPLE)",
        active_ingredient="Metalaxyl + Mancozeb",
        formulation="WP",
        application_method="Foliar spray",
        approved_crop="Tomato",
        approved_target="Late Blight (Phytophthora infestans)",
        label_rate="2.5 g/L of water",
        pre_harvest_interval_days=14,
        reentry_interval_hours=24,
        safety_information=(
            "SAMPLE DATA — Systemic + contact fungicide. Wear full PPE. "
            "Do not apply more than 3 sprays per season to manage resistance."
        ),
        source="SAMPLE — Based on CIBRC India registrations (demo only)",
        verification_date="2024-01-15",
        is_organic_certified=False,
        contraindications=["Limit to 3 applications per season"],
    ),
    # ---- Potato — Early Blight ----
    VerifiedTreatmentRecord(
        crop="potato",
        target_pest_or_disease="early_blight",
        product="Mancozeb 75% WP (SAMPLE)",
        active_ingredient="Mancozeb",
        formulation="WP",
        application_method="Foliar spray",
        approved_crop="Potato",
        approved_target="Early Blight (Alternaria solani)",
        label_rate="2.5 g/L of water",
        pre_harvest_interval_days=7,
        reentry_interval_hours=24,
        safety_information=(
            "SAMPLE DATA — Wear protective clothing and mask. "
            "Avoid spray drift near water bodies."
        ),
        source="SAMPLE — Based on CIBRC India registrations (demo only)",
        verification_date="2024-01-15",
        is_organic_certified=False,
        contraindications=["Do not mix with alkaline pesticides"],
    ),
    # ---- Potato — Late Blight ----
    VerifiedTreatmentRecord(
        crop="potato",
        target_pest_or_disease="late_blight",
        product="Cymoxanil 8% + Mancozeb 64% WP (SAMPLE)",
        active_ingredient="Cymoxanil + Mancozeb",
        formulation="WP",
        application_method="Foliar spray",
        approved_crop="Potato",
        approved_target="Late Blight (Phytophthora infestans)",
        label_rate="3.0 g/L of water",
        pre_harvest_interval_days=14,
        reentry_interval_hours=24,
        safety_information=(
            "SAMPLE DATA — Systemic + contact fungicide. Full PPE required. "
            "Maximum 3 applications per season."
        ),
        source="SAMPLE — Based on CIBRC India registrations (demo only)",
        verification_date="2024-01-15",
        is_organic_certified=False,
        contraindications=["Limit to 3 applications per season"],
    ),
]


class TreatmentDatabase:
    """
    Lightweight in-memory treatment knowledge store.

    Stores verified treatment records indexed by (crop, disease/pest) pairs.
    Returns empty results (with a safe message) when no verified data is available
    rather than inventing recommendations.
    """

    NO_VERIFIED_RECOMMENDATION = "no verified recommendation"

    def __init__(self, records: Optional[List[VerifiedTreatmentRecord]] = None) -> None:
        self._index: Dict[Tuple[str, str], List[VerifiedTreatmentRecord]] = {}
        initial_records = records if records is not None else _SAMPLE_RECORDS
        for record in initial_records:
            self.add_record(record)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_record(self, record: VerifiedTreatmentRecord) -> None:
        """Add a single verified treatment record to the database."""
        key = self._make_key(record.crop, record.target_pest_or_disease)
        self._index.setdefault(key, []).append(record)

    def add_records(self, records: List[VerifiedTreatmentRecord]) -> None:
        """Bulk-add verified treatment records."""
        for record in records:
            self.add_record(record)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def lookup(
        self,
        crop: str,
        disease_or_pest: str,
    ) -> List[VerifiedTreatmentRecord]:
        """
        Retrieve verified treatment records for a given crop and disease/pest.

        Returns an empty list if no verified records exist.
        Callers should interpret an empty list as "no verified recommendation".
        """
        key = self._make_key(crop, disease_or_pest)
        return list(self._index.get(key, []))

    def lookup_safe(
        self,
        crop: str,
        disease_or_pest: str,
    ) -> Dict:
        """
        Retrieve treatments with an explicit safety wrapper.

        Returns a dict with:
          - "found": bool
          - "records": list of VerifiedTreatmentRecord dicts
          - "message": str — either a summary or "no verified recommendation"
          - "disclaimer": str — always present
        """
        records = self.lookup(crop, disease_or_pest)
        if records:
            return {
                "found": True,
                "records": [r.model_dump() for r in records],
                "message": (
                    f"Found {len(records)} verified treatment(s) for "
                    f"{crop} / {disease_or_pest}."
                ),
                "disclaimer": (
                    "SAMPLE/DEMO DATA ONLY — These records are for prototype "
                    "demonstration. Verify with local agricultural authorities "
                    "before any field application."
                ),
            }
        return {
            "found": False,
            "records": [],
            "message": self.NO_VERIFIED_RECOMMENDATION,
            "disclaimer": (
                "No verified treatment record is available for this "
                "crop-disease/pest combination. Do NOT use unverified suggestions."
            ),
        }

    def list_available_keys(self) -> List[Tuple[str, str]]:
        """Return all (crop, disease_or_pest) keys that have records."""
        return list(self._index.keys())

    @property
    def total_records(self) -> int:
        """Total number of treatment records stored."""
        return sum(len(v) for v in self._index.values())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _make_key(crop: str, disease_or_pest: str) -> Tuple[str, str]:
        """Normalize lookup key to lowercase, stripped."""
        return (crop.strip().lower(), disease_or_pest.strip().lower())


@lru_cache()
def get_treatment_database() -> TreatmentDatabase:
    """Return a singleton TreatmentDatabase pre-loaded with sample data."""
    return TreatmentDatabase()
