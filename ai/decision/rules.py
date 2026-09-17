"""
Deterministic Decision Rules and Precedence Evaluator for Person 3 Decision Engine.
Evaluates FieldAnalysisOutput and environmental telemetry to produce DecisionResult.
"""

from typing import Any, Dict, List, Optional, Tuple
from .config import DecisionSettings, get_decision_settings
from .schemas import ActionType, DecisionAudit, DecisionResult, PriorityLevel, SafetyStatus


class RuleEvaluator:
    """
    Deterministic rule engine implementing precedence-ordered evaluation.
    """

    def __init__(self, settings: Optional[DecisionSettings] = None):
        self.settings = settings or get_decision_settings()

    def evaluate_rules(
        self,
        analysis_dict: Dict[str, Any],
        sensor_data: Optional[Dict[str, Any]] = None,
        weather_data: Optional[Dict[str, Any]] = None,
        crop_stage: str = "vegetative",
    ) -> DecisionResult:
        """
        Evaluate precedence rules on structured analysis dict and telemetry.
        """
        triggered_rules: List[str] = []

        # Extract blocks from analysis_dict safely
        crop_block = analysis_dict.get("crop") or {}
        disease_block = analysis_dict.get("disease")
        pests_list = analysis_dict.get("pests") or []
        nutrient_str = analysis_dict.get("nutrient_deficiency")
        severity_block = analysis_dict.get("severity") or {}
        climate_block = analysis_dict.get("climate_risk") or {}
        requires_conf = bool(analysis_dict.get("requires_confirmation", False))
        metadata = analysis_dict.get("metadata") or {}

        crop_name = crop_block.get("name", "unknown") if isinstance(crop_block, dict) else "unknown"
        crop_conf = float(crop_block.get("confidence", 1.0)) if isinstance(crop_block, dict) else 1.0

        # Extract telemetry details
        soil_moisture = self._extract_soil_moisture(sensor_data, metadata)
        rain_24h = self._extract_rain_24h(weather_data, sensor_data, metadata)

        # Inputs summary for audit trail
        inputs_considered = {
            "crop": crop_name,
            "crop_confidence": crop_conf,
            "disease": disease_block.get("name") if isinstance(disease_block, dict) else None,
            "pests_count": len(pests_list) if isinstance(pests_list, list) else 0,
            "nutrient_deficiency": nutrient_str,
            "severity_level": severity_block.get("level") if isinstance(severity_block, dict) else None,
            "soil_moisture_percent": soil_moisture,
            "rain_24h_mm": rain_24h,
            "requires_confirmation": requires_conf,
        }

        # ----------------------------------------------------------------------
        # RULE 1: Confirmation Required / Low Confidence Check
        # ----------------------------------------------------------------------
        disease_conf = float(disease_block.get("confidence", 1.0)) if isinstance(disease_block, dict) else 1.0
        if (
            requires_conf
            or crop_conf < self.settings.LOW_CONFIDENCE_THRESHOLD
            or disease_conf < self.settings.LOW_CONFIDENCE_THRESHOLD
        ):
            triggered_rules.append("RULE_CONFIRMATION_REQUIRED")
            min_conf = min(crop_conf, disease_conf)
            return DecisionResult(
                action=ActionType.WARN,
                reason=(
                    f"AI diagnosis confidence ({min_conf:.0%}) is below high reliability threshold "
                    f"({self.settings.LOW_CONFIDENCE_THRESHOLD:.0%}) or flagged for review. "
                    "On-field expert confirmation required before taking automated action."
                ),
                priority=PriorityLevel.HIGH,
                requires_confirmation=True,
                safety_status=SafetyStatus.CONFIRMATION_REQUIRED,
                audit=DecisionAudit(
                    triggered_rules=triggered_rules,
                    inputs_considered=inputs_considered,
                ),
            )

        # ----------------------------------------------------------------------
        # RULE 2: Disease or Pest Detection -> Evaluate Treatment & Weather
        # ----------------------------------------------------------------------
        has_active_disease = (
            isinstance(disease_block, dict)
            and disease_block.get("name")
            and disease_block.get("name") != "healthy"
        )
        has_active_pest = bool(pests_list)

        if has_active_disease or has_active_pest:
            target_name = (
                disease_block.get("name") if has_active_disease else "pest_infestation"
            )
            severity_level = (
                severity_block.get("level", "moderate") if isinstance(severity_block, dict) else "moderate"
            )

            # Retrieve verified treatment from metadata or RAG
            treatment_record = self._extract_treatment_record(metadata)

            # Check if verified treatment is available
            if not treatment_record:
                triggered_rules.append("RULE_NO_VERIFIED_TREATMENT")
                return DecisionResult(
                    action=ActionType.WARN,
                    reason=(
                        f"Detected {target_name.replace('_', ' ')} on {crop_name}, but no verified "
                        "treatment recommendation is available in the knowledge database. "
                        "Spraying blocked to prevent off-label pesticide usage."
                    ),
                    priority=PriorityLevel.HIGH,
                    requires_confirmation=True,
                    safety_status=SafetyStatus.NO_VERIFIED_TREATMENT,
                    audit=DecisionAudit(
                        triggered_rules=triggered_rules,
                        inputs_considered=inputs_considered,
                    ),
                )

            # Check weather suitability for spraying
            flood_risk = float(climate_block.get("flood", 0.0))
            waterlog_risk = float(climate_block.get("waterlogging", 0.0))
            rain_unsuitable = rain_24h is not None and rain_24h >= self.settings.PRECIPITATION_SPRAY_BLOCK_THRESHOLD
            climate_unsuitable = (
                flood_risk >= self.settings.FLOOD_RISK_BLOCK_THRESHOLD
                or waterlog_risk >= self.settings.WATERLOGGING_RISK_BLOCK_THRESHOLD
            )

            product_name = treatment_record.get("product", "Verified Treatment")

            if rain_unsuitable or climate_unsuitable:
                triggered_rules.append("RULE_SPRAY_DELAY_WEATHER")
                delay_reason = (
                    f"High precipitation forecast ({rain_24h:.1f}mm)"
                    if rain_unsuitable
                    else f"Elevated flood/waterlogging risk ({max(flood_risk, waterlog_risk):.0%})"
                )
                priority = (
                    PriorityLevel.HIGH if severity_level in ["high", "critical"] else PriorityLevel.MEDIUM
                )
                return DecisionResult(
                    action=ActionType.DELAY,
                    reason=(
                        f"Target condition '{target_name.replace('_', ' ')}' identified with verified treatment "
                        f"({product_name}), but application is DELAYED due to unsuitable weather: {delay_reason}."
                    ),
                    priority=priority,
                    requires_confirmation=False,
                    safety_status=SafetyStatus.WEATHER_DELAY,
                    verified_treatment=treatment_record,
                    audit=DecisionAudit(
                        triggered_rules=triggered_rules,
                        inputs_considered=inputs_considered,
                    ),
                )

            # Suitable environment -> Recommend SPRAY
            triggered_rules.append("RULE_RECOMMEND_SPRAY")
            priority = (
                PriorityLevel.HIGH if severity_level in ["high", "critical"] else PriorityLevel.MEDIUM
            )
            return DecisionResult(
                action=ActionType.SPRAY,
                reason=(
                    f"Verified spray recommended for {crop_name} target '{target_name.replace('_', ' ')}' "
                    f"using {product_name}. Environmental conditions are suitable for foliar application."
                ),
                priority=priority,
                requires_confirmation=False,
                safety_status=SafetyStatus.SAFE_TO_SPRAY,
                verified_treatment=treatment_record,
                audit=DecisionAudit(
                    triggered_rules=triggered_rules,
                    inputs_considered=inputs_considered,
                ),
            )

        # ----------------------------------------------------------------------
        # RULE 3: Water Stress / Soil Moisture -> Evaluate Irrigation
        # ----------------------------------------------------------------------
        drought_risk = float(climate_block.get("drought", 0.0))
        is_low_moisture = (
            soil_moisture is not None
            and soil_moisture < self.settings.SOIL_MOISTURE_IRRIGATE_THRESHOLD
        )
        is_drought_stressed = (
            drought_risk >= self.settings.DROUGHT_RISK_IRRIGATE_THRESHOLD
            and (soil_moisture is None or soil_moisture < 50.0)
        )

        if is_low_moisture or is_drought_stressed:
            # Check irrigation safety blockers (saturated soil, high flood/waterlogging risk)
            flood_risk = float(climate_block.get("flood", 0.0))
            waterlog_risk = float(climate_block.get("waterlogging", 0.0))
            is_saturated = (
                soil_moisture is not None
                and soil_moisture >= self.settings.SOIL_MOISTURE_SATURATED_THRESHOLD
            )
            is_high_water_hazard = (
                flood_risk >= self.settings.FLOOD_RISK_BLOCK_THRESHOLD
                or waterlog_risk >= self.settings.WATERLOGGING_RISK_BLOCK_THRESHOLD
            )

            if not is_saturated and not is_high_water_hazard:
                triggered_rules.append("RULE_RECOMMEND_IRRIGATE")
                priority = PriorityLevel.HIGH if drought_risk >= 0.70 else PriorityLevel.MEDIUM
                moist_str = f"{soil_moisture:.1f}%" if soil_moisture is not None else "unmonitored"
                return DecisionResult(
                    action=ActionType.IRRIGATE,
                    reason=(
                        f"Soil moisture ({moist_str}) and drought risk ({drought_risk:.0%}) indicate water stress. "
                        f"Controlled irrigation cycle recommended for {self.settings.DEFAULT_IRRIGATION_DURATION_MINUTES:.0f} minutes."
                    ),
                    priority=priority,
                    requires_confirmation=False,
                    safety_status=SafetyStatus.SAFE_TO_IRRIGATE,
                    duration_minutes=self.settings.DEFAULT_IRRIGATION_DURATION_MINUTES,
                    audit=DecisionAudit(
                        triggered_rules=triggered_rules,
                        inputs_considered=inputs_considered,
                    ),
                )

        # ----------------------------------------------------------------------
        # RULE 4: Healthy Field -> NO_ACTION
        # ----------------------------------------------------------------------
        triggered_rules.append("RULE_NO_ACTION")
        return DecisionResult(
            action=ActionType.NO_ACTION,
            reason=(
                f"Crop '{crop_name}' appears healthy with no active disease/pest infestation, "
                "normal soil moisture, and low environmental climate risk. No operational intervention required."
            ),
            priority=PriorityLevel.LOW,
            requires_confirmation=False,
            safety_status=SafetyStatus.FIELD_HEALTHY,
            audit=DecisionAudit(
                triggered_rules=triggered_rules,
                inputs_considered=inputs_considered,
            ),
        )

    # --------------------------------------------------------------------------
    # Helper extraction methods
    # --------------------------------------------------------------------------

    @staticmethod
    def _extract_soil_moisture(
        sensor_data: Optional[Dict[str, Any]], metadata: Dict[str, Any]
    ) -> Optional[float]:
        """Extract soil moisture percentage from telemetry or metadata."""
        if isinstance(sensor_data, dict):
            if "soil" in sensor_data and isinstance(sensor_data["soil"], dict):
                val = sensor_data["soil"].get("moisture_percent")
                if val is not None:
                    return float(val)
            elif "moisture_percent" in sensor_data:
                return float(sensor_data["moisture_percent"])

        # Check metadata fallback
        climate_details = metadata.get("climate_details")
        if isinstance(climate_details, dict):
            val = climate_details.get("soil_moisture_percent")
            if val is not None:
                return float(val)
        return None

    @staticmethod
    def _extract_rain_24h(
        weather_data: Optional[Dict[str, Any]],
        sensor_data: Optional[Dict[str, Any]],
        metadata: Dict[str, Any],
    ) -> Optional[float]:
        """Extract expected 24h precipitation in mm."""
        if isinstance(weather_data, dict):
            if "upcoming_24h_rainfall_mm" in weather_data:
                return float(weather_data["upcoming_24h_rainfall_mm"])
            elif "rainfall_mm" in weather_data:
                return float(weather_data["rainfall_mm"])

        if isinstance(sensor_data, dict):
            air = sensor_data.get("air")
            if isinstance(air, dict) and "rainfall_mm" in air:
                return float(air["rainfall_mm"])

        return None

    @staticmethod
    def _extract_treatment_record(metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract verified treatment dictionary from pipeline metadata."""
        kb_data = metadata.get("knowledge_retrieval")
        if isinstance(kb_data, dict) and kb_data.get("found"):
            records = kb_data.get("records")
            if isinstance(records, list) and len(records) > 0:
                first_rec = records[0]
                if isinstance(first_rec, dict):
                    return first_rec

        # Fallback check for direct treatments list in metadata
        treatments = metadata.get("treatments")
        if isinstance(treatments, list) and len(treatments) > 0:
            if isinstance(treatments[0], dict):
                return treatments[0]

        return None
