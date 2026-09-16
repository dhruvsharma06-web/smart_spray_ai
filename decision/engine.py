import logging
from typing import Any, Dict, List
try:
    from .models import (
        ActionType,
        DecisionAction,
        DecisionRequest,
        DecisionResponse,
        PrimaryDecision,
        Priority,
        RiskLevel,
    )
except ImportError:
    from models import (
        ActionType,
        DecisionAction,
        DecisionRequest,
        DecisionResponse,
        PrimaryDecision,
        Priority,
        RiskLevel,
    )

logger = logging.getLogger("decision-engine")


class DecisionEngine:
    """
    Deterministic Agronomic Decision Engine.
    Evaluates crop health diagnostics, sensor readings, and meteorological forecasts
    to recommend agricultural interventions according to strict priority rules.
    """

    def evaluate(self, request: DecisionRequest) -> DecisionResponse:
        analysis = request.analysis or {}
        sensor_data = request.sensor_data or {}
        weather_data = request.weather_data or {}

        # 1. Extract telemetry and risk vectors
        climate_risk = analysis.get("climate_risk") or {}
        drought_risk = float(climate_risk.get("drought", 0.0) or 0.0)
        heat_risk = float(climate_risk.get("heat", 0.0) or 0.0)
        flood_risk = float(climate_risk.get("flood", 0.0) or 0.0)

        rain_prob = float(weather_data.get("rain_probability", 0.0) or 0.0)
        rainfall_mm = float(weather_data.get("rainfall", 0.0) or 0.0)
        air_temp = float(weather_data.get("temperature", 25.0) or 25.0)

        soil = sensor_data.get("soil") or {}
        soil_moisture = soil.get("moisture_percent") or soil.get("moisture")
        if soil_moisture is not None:
            soil_moisture = float(soil_moisture)

        # 2. Extract disease and pest diagnostics
        crop = analysis.get("crop") or {}
        crop_name = crop.get("name") or "crop"
        crop_conf = float(crop.get("confidence", 1.0) or 1.0)

        disease = analysis.get("disease") or {}
        disease_name = disease.get("name") if isinstance(disease, dict) else None
        disease_conf = float(disease.get("confidence", 0.0) or 0.0) if isinstance(disease, dict) else 0.0
        disease_affected_area = float(disease.get("affected_area_percent", 0.0) or 0.0) if isinstance(disease, dict) else 0.0

        pests = analysis.get("pests") or []
        severity = analysis.get("severity") or {}
        severity_level = (severity.get("level") or (disease.get("severity") if isinstance(disease, dict) else "") or "").lower()
        if not severity_level and disease_affected_area > 0:
            if disease_affected_area >= 50:
                severity_level = "critical"
            elif disease_affected_area >= 20:
                severity_level = "high"
            elif disease_affected_area >= 10:
                severity_level = "moderate"
            else:
                severity_level = "low"

        nutrient = analysis.get("nutrient_deficiency")
        ai_requires_confirmation = bool(analysis.get("requires_confirmation", False))

        warnings: List[str] = []
        requires_confirmation = ai_requires_confirmation

        # Check for diagnostic ambiguity
        if crop_conf < 0.60 or (disease_name and disease_conf > 0 and disease_conf < 0.60):
            requires_confirmation = True
            warnings.append("Low diagnostic confidence detected. Confirmation recommended before actuation.")

        # -------------------------------------------------------------
        # RULE 1: WEATHER / RAIN DELAY
        # Spraying during rain causes immediate chemical wash-off and environmental runoff.
        # -------------------------------------------------------------
        if rain_prob >= 70.0 or rainfall_mm > 5.0:
            warnings.append("Heavy rainfall expected. Delay spraying to avoid wash-off and chemical runoff.")
            return DecisionResponse(
                primary_decision=PrimaryDecision.DELAY_SPRAY,
                risk_level=RiskLevel.HIGH,
                actions=[DecisionAction(type=ActionType.DELAY_SPRAY, priority=Priority.HIGH)],
                warnings=warnings,
                requires_confirmation=requires_confirmation,
            )

        # -------------------------------------------------------------
        # RULE 2: SEVERE DROUGHT / IRRIGATION NEED
        # Water stress must be addressed before applying systemic foliar chemicals.
        # -------------------------------------------------------------
        if drought_risk >= 0.80 or (soil_moisture is not None and soil_moisture < 20.0):
            warnings.append("Low moisture / high drought risk detected. Irrigation required.")
            return DecisionResponse(
                primary_decision=PrimaryDecision.IRRIGATE,
                risk_level=RiskLevel.HIGH,
                actions=[DecisionAction(type=ActionType.IRRIGATION, priority=Priority.HIGH)],
                warnings=warnings,
                requires_confirmation=requires_confirmation,
            )

        # -------------------------------------------------------------
        # RULE 3: EXTREME HEAT STRESS
        # High heat increases chemical droplet evaporation and crop phytotoxicity.
        # -------------------------------------------------------------
        if heat_risk >= 0.85 or air_temp >= 38.0:
            warnings.append("Extreme heat stress detected. Delay spraying until cooler hours to avoid crop scorch.")
            if disease_name and disease_name != "healthy":
                return DecisionResponse(
                    primary_decision=PrimaryDecision.DELAY_SPRAY,
                    risk_level=RiskLevel.HIGH,
                    actions=[DecisionAction(type=ActionType.DELAY_SPRAY, priority=Priority.MEDIUM)],
                    warnings=warnings,
                    requires_confirmation=requires_confirmation,
                )
            return DecisionResponse(
                primary_decision=PrimaryDecision.WARN,
                risk_level=RiskLevel.HIGH,
                actions=[DecisionAction(type=ActionType.WARN, priority=Priority.MEDIUM)],
                warnings=warnings,
                requires_confirmation=requires_confirmation,
            )

        # -------------------------------------------------------------
        # RULE 4: SEVERE DISEASE OR CRITICAL PEST INFESTATION
        # Immediate targeted spray required to stop pathogen progression.
        # -------------------------------------------------------------
        has_disease = bool(disease_name and disease_name != "healthy" and disease_name != "none")
        has_pests = bool(pests and len(pests) > 0)

        if has_disease and severity_level in ("critical", "high"):
            warnings.append(f"High severity {disease_name} infection detected on {crop_name}. Immediate treatment recommended.")
            return DecisionResponse(
                primary_decision=PrimaryDecision.SPRAY,
                risk_level=RiskLevel.HIGH,
                actions=[DecisionAction(type=ActionType.SPRAY, priority=Priority.HIGH)],
                warnings=warnings,
                requires_confirmation=requires_confirmation,
            )

        # Significant pest count or high pest severity
        total_pest_count = sum(int(p.get("count", 1) or 1) for p in pests) if has_pests else 0
        if has_pests and total_pest_count >= 10:
            pest_title = pests[0].get("name") or pests[0].get("pest_type") or "pests"
            warnings.append(f"Significant pest infestation ({pest_title}, count: {total_pest_count}) detected. Treatment recommended.")
            return DecisionResponse(
                primary_decision=PrimaryDecision.SPRAY,
                risk_level=RiskLevel.HIGH,
                actions=[DecisionAction(type=ActionType.SPRAY, priority=Priority.HIGH)],
                warnings=warnings,
                requires_confirmation=requires_confirmation,
            )

        # -------------------------------------------------------------
        # RULE 5: MODERATE DISEASE OR PEST DETECTION
        # Standard controlled spray application.
        # -------------------------------------------------------------
        if has_disease or has_pests:
            dis_label = disease_name or (pests[0].get("name") if pests else "target condition")
            return DecisionResponse(
                primary_decision=PrimaryDecision.SPRAY,
                risk_level=RiskLevel.MEDIUM,
                actions=[DecisionAction(type=ActionType.SPRAY, priority=Priority.MEDIUM)],
                warnings=warnings,
                requires_confirmation=requires_confirmation,
            )

        # -------------------------------------------------------------
        # RULE 6: NUTRIENT DEFICIENCY (WITHOUT DISEASE)
        # Warn farmer for fertilization without spraying pesticide.
        # -------------------------------------------------------------
        if nutrient:
            nutr_label = nutrient if isinstance(nutrient, str) else nutrient.get("primary_deficiency", "nutrient")
            warnings.append(f"Visual nutrient deficiency symptoms ({nutr_label}) detected. Soil testing recommended.")
            return DecisionResponse(
                primary_decision=PrimaryDecision.WARN,
                risk_level=RiskLevel.LOW,
                actions=[DecisionAction(type=ActionType.WARN, priority=Priority.LOW)],
                warnings=warnings,
                requires_confirmation=requires_confirmation,
            )

        # -------------------------------------------------------------
        # RULE 7: HEALTHY / BASELINE MONITORING
        # No interventions needed; continue normal observation.
        # -------------------------------------------------------------
        is_explicitly_healthy = (
            disease_name == "healthy"
            or (isinstance(disease, dict) and disease.get("is_healthy") is True)
        )
        if is_explicitly_healthy:
            return DecisionResponse(
                primary_decision=PrimaryDecision.MONITOR,
                risk_level=RiskLevel.LOW,
                actions=[DecisionAction(type=ActionType.MONITOR, priority=Priority.LOW)],
                warnings=warnings if warnings else ["Crops and foliage appear healthy. Continue regular field monitoring."],
                requires_confirmation=requires_confirmation,
            )

        # -------------------------------------------------------------
        # DEFAULT: PROACTIVE SPRAY / GENERAL ACTION
        # Matches prototype decision engine default when no severe conditions apply
        # -------------------------------------------------------------
        return DecisionResponse(
            primary_decision=PrimaryDecision.SPRAY,
            risk_level=RiskLevel.MEDIUM,
            actions=[DecisionAction(type=ActionType.SPRAY, priority=Priority.MEDIUM)],
            warnings=warnings,
            requires_confirmation=requires_confirmation,
        )


decision_engine = DecisionEngine()
