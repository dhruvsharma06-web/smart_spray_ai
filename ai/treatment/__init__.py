"""
Treatment Knowledge Package.
Provides a lightweight verified treatment database and retrieval interface.
"""

from .database import TreatmentDatabase, get_treatment_database

__all__ = ["TreatmentDatabase", "get_treatment_database"]
