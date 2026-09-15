"""
Tests for the AI Knowledge Layer — TreatmentDatabase and KnowledgeBase.
"""

import pytest

from ai.schemas.treatment import VerifiedTreatmentRecord
from ai.treatment.database import TreatmentDatabase
from ai.rag.knowledge_base import KnowledgeBase, KnowledgeSource, KnowledgeResponse


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture
def empty_db() -> TreatmentDatabase:
    """A TreatmentDatabase with no records."""
    return TreatmentDatabase(records=[])


@pytest.fixture
def sample_db() -> TreatmentDatabase:
    """A TreatmentDatabase loaded with default sample data."""
    return TreatmentDatabase()


@pytest.fixture
def kb(sample_db: TreatmentDatabase) -> KnowledgeBase:
    """A KnowledgeBase wrapping the sample database."""
    return KnowledgeBase(treatment_db=sample_db)


@pytest.fixture
def empty_kb(empty_db: TreatmentDatabase) -> KnowledgeBase:
    """A KnowledgeBase with no records."""
    return KnowledgeBase(treatment_db=empty_db)


# =====================================================================
# TreatmentDatabase Tests
# =====================================================================


class TestTreatmentDatabase:
    """Tests for TreatmentDatabase."""

    def test_sample_data_loaded(self, sample_db: TreatmentDatabase):
        """Default database loads sample records."""
        assert sample_db.total_records >= 5

    def test_empty_database(self, empty_db: TreatmentDatabase):
        """Empty database has zero records."""
        assert empty_db.total_records == 0

    def test_lookup_existing_crop_disease(self, sample_db: TreatmentDatabase):
        """Lookup returns records for a known crop + disease."""
        results = sample_db.lookup("tomato", "early_blight")
        assert len(results) >= 1
        for r in results:
            assert r.crop == "tomato"
            assert r.target_pest_or_disease == "early_blight"

    def test_lookup_case_insensitive(self, sample_db: TreatmentDatabase):
        """Lookup normalizes case."""
        results = sample_db.lookup("Tomato", "Early_Blight")
        assert len(results) >= 1

    def test_lookup_whitespace_trimmed(self, sample_db: TreatmentDatabase):
        """Lookup strips whitespace from keys."""
        results = sample_db.lookup("  tomato  ", "  early_blight  ")
        assert len(results) >= 1

    def test_lookup_missing_returns_empty(self, sample_db: TreatmentDatabase):
        """Lookup returns empty list for unknown combinations."""
        results = sample_db.lookup("mango", "anthracnose")
        assert results == []

    def test_lookup_healthy_returns_empty(self, sample_db: TreatmentDatabase):
        """No treatment records for 'healthy' — healthy plants don't need treatment."""
        results = sample_db.lookup("tomato", "healthy")
        assert results == []

    def test_lookup_safe_found(self, sample_db: TreatmentDatabase):
        """lookup_safe returns a structured dict with found=True."""
        result = sample_db.lookup_safe("tomato", "late_blight")
        assert result["found"] is True
        assert len(result["records"]) >= 1
        assert "disclaimer" in result
        assert "SAMPLE" in result["disclaimer"]

    def test_lookup_safe_not_found(self, sample_db: TreatmentDatabase):
        """lookup_safe returns no verified recommendation when missing."""
        result = sample_db.lookup_safe("wheat", "rust")
        assert result["found"] is False
        assert result["records"] == []
        assert result["message"] == TreatmentDatabase.NO_VERIFIED_RECOMMENDATION

    def test_add_record(self, empty_db: TreatmentDatabase):
        """Can add a record to the database."""
        record = VerifiedTreatmentRecord(
            crop="rice",
            target_pest_or_disease="blast",
            product="Tricyclazole 75% WP (SAMPLE)",
            active_ingredient="Tricyclazole",
            formulation="WP",
            application_method="Foliar spray",
            approved_crop="Rice",
            approved_target="Blast (Magnaporthe oryzae)",
            label_rate="0.6 g/L of water",
            pre_harvest_interval_days=21,
            safety_information="SAMPLE DATA — Wear PPE during application.",
            source="SAMPLE — Demo record",
            verification_date="2024-06-01",
        )
        empty_db.add_record(record)
        assert empty_db.total_records == 1
        results = empty_db.lookup("rice", "blast")
        assert len(results) == 1
        assert results[0].active_ingredient == "Tricyclazole"

    def test_add_records_bulk(self, empty_db: TreatmentDatabase):
        """Can bulk-add records."""
        records = [
            VerifiedTreatmentRecord(
                crop="rice",
                target_pest_or_disease="blast",
                product=f"Product {i} (SAMPLE)",
                active_ingredient=f"Ingredient {i}",
                formulation="WP",
                application_method="Foliar spray",
                approved_crop="Rice",
                approved_target="Blast",
                label_rate="1.0 g/L",
                pre_harvest_interval_days=7,
                safety_information="SAMPLE DATA",
                source="SAMPLE — Demo",
                verification_date="2024-06-01",
            )
            for i in range(3)
        ]
        empty_db.add_records(records)
        assert empty_db.total_records == 3

    def test_list_available_keys(self, sample_db: TreatmentDatabase):
        """Lists all available (crop, disease) keys."""
        keys = sample_db.list_available_keys()
        assert len(keys) >= 4
        assert ("tomato", "early_blight") in keys
        assert ("potato", "late_blight") in keys

    def test_all_sample_records_marked_sample(self, sample_db: TreatmentDatabase):
        """Every sample record must contain 'SAMPLE' in source and safety_information."""
        for key in sample_db.list_available_keys():
            records = sample_db.lookup(*key)
            for r in records:
                assert "SAMPLE" in r.source, f"Record source not marked SAMPLE: {r.source}"
                assert "SAMPLE" in r.safety_information, (
                    f"Record safety_information not marked SAMPLE: {r.safety_information}"
                )

    def test_sample_records_have_valid_phi(self, sample_db: TreatmentDatabase):
        """All sample records have non-negative PHI."""
        for key in sample_db.list_available_keys():
            for r in sample_db.lookup(*key):
                assert r.pre_harvest_interval_days >= 0

    def test_potato_records_exist(self, sample_db: TreatmentDatabase):
        """Potato early blight and late blight have records."""
        assert len(sample_db.lookup("potato", "early_blight")) >= 1
        assert len(sample_db.lookup("potato", "late_blight")) >= 1


# =====================================================================
# KnowledgeBase Tests
# =====================================================================


class TestKnowledgeBase:
    """Tests for the RAG-style KnowledgeBase."""

    def test_query_found(self, kb: KnowledgeBase):
        """Query returns verified records when available."""
        response = kb.query("tomato", "early_blight")
        assert isinstance(response, KnowledgeResponse)
        assert response.found is True
        assert response.source == KnowledgeSource.VERIFIED_DATABASE
        assert len(response.records) >= 1
        assert "SAMPLE" in response.disclaimer

    def test_query_not_found(self, kb: KnowledgeBase):
        """Query returns safe fallback when no records exist."""
        response = kb.query("sugarcane", "red_rot")
        assert response.found is False
        assert response.source == KnowledgeSource.NO_DATA
        assert response.records == []
        assert response.message == TreatmentDatabase.NO_VERIFIED_RECOMMENDATION

    def test_query_preserves_query_params(self, kb: KnowledgeBase):
        """Response includes the original query parameters."""
        response = kb.query("potato", "late_blight")
        assert response.query == {"crop": "potato", "disease_or_pest": "late_blight"}

    def test_to_dict_serialization(self, kb: KnowledgeBase):
        """KnowledgeResponse serializes to a complete dict."""
        response = kb.query("tomato", "late_blight")
        d = response.to_dict()
        assert d["source"] == "verified_database"
        assert d["found"] is True
        assert isinstance(d["records"], list)
        assert "message" in d
        assert "disclaimer" in d
        assert "query" in d

    def test_to_dict_not_found(self, kb: KnowledgeBase):
        """Serialized not-found response has expected shape."""
        d = kb.query("unknown", "unknown").to_dict()
        assert d["source"] == "no_data"
        assert d["found"] is False
        assert d["records"] == []

    def test_list_available(self, kb: KnowledgeBase):
        """list_available returns crop + disease_or_pest pairs."""
        available = kb.list_available()
        assert len(available) >= 4
        assert all("crop" in item and "disease_or_pest" in item for item in available)

    def test_total_records(self, kb: KnowledgeBase):
        """total_records matches underlying database."""
        assert kb.total_records >= 5

    def test_empty_kb_returns_no_data(self, empty_kb: KnowledgeBase):
        """Empty knowledge base always returns no_data."""
        response = empty_kb.query("tomato", "early_blight")
        assert response.found is False
        assert response.source == KnowledgeSource.NO_DATA

    def test_disclaimer_always_present(self, kb: KnowledgeBase):
        """Disclaimer is present in both found and not-found responses."""
        found = kb.query("tomato", "early_blight")
        not_found = kb.query("wheat", "rust")
        assert found.disclaimer != ""
        assert not_found.disclaimer != ""

    def test_records_are_verified_treatment_records(self, kb: KnowledgeBase):
        """Returned records are proper VerifiedTreatmentRecord instances."""
        response = kb.query("tomato", "early_blight")
        for record in response.records:
            assert isinstance(record, VerifiedTreatmentRecord)
            assert record.crop == "tomato"
            assert record.target_pest_or_disease == "early_blight"
