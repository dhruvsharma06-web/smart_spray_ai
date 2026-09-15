"""
Severity assessment package and factory.
"""

from typing import Optional
from .base import BaseSeverityEstimator
from .estimator import CompositeSeverityEstimator

__all__ = [
    "BaseSeverityEstimator",
    "CompositeSeverityEstimator",
    "get_severity_estimator",
]


def get_severity_estimator() -> BaseSeverityEstimator:
    """
    Factory returning severity estimator instance.
    """
    return CompositeSeverityEstimator()
