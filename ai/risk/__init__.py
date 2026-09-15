"""
Climate-Risk AI Package.
Provides transparent rule-based risk evaluation for drought, heat, flood, and waterlogging.
"""

from .climate_risk import ClimateRiskEngine, get_climate_risk_engine

__all__ = ["ClimateRiskEngine", "get_climate_risk_engine"]
