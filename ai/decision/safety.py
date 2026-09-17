"""
Safety Layer for Person 3 Decision Engine.
Implements fail-safe checks, telemetry range validation, and safety blocks.
Ensures no dangerous automatic actuation occurs when inputs are invalid or unsafe.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from .config import DecisionSettings, get_decision_settings
from .schemas import ActionType, DecisionAudit, DecisionResult, PriorityLevel, SafetyStatus


@dataclass
class SafetyCheckResult:
    """Result of safety layer evaluation."""

    is_safe: bool
    status: SafetyStatus
    block_reason: str
    triggered_safety_rules: List[str]


class SafetyChecker:
    """
    Evaluates telemetry validity, sensor boundaries, and critical safety hazards.
    """

    def __init__(self, settings: Optional[DecisionSettings] = None):
        self.settings = settings or get_decision_settings()

    def validate_telemetry(self, sensor_data: Optional[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        Validate sensor telemetry ranges.

        Returns (is_valid, error_message).
        """
        if sensor_data is None:
            return True, "No direct sensor payload provided; evaluated with defaults."

        if not isinstance(sensor_data, dict):
            return False, f"Invalid sensor payload format: expected dict, got {type(sensor_data).__name__}"

        # Check soil sensor data if present
        soil = sensor_data.get("soil")
        if isinstance(soil, dict):
            moisture = soil.get("moisture_percent")
            if moisture is not None:
                if not (0.0 <= float(moisture) <= 100.0):
                    return False, f"Soil moisture out of bounds [0-100%]: {moisture}"

            temp = soil.get("temperature_celsius")
            if temp is not None:
                if not (-20.0 <= float(temp) <= 70.0):
                    return False, f"Soil temperature out of bounds [-20 to +70°C]: {temp}"

        # Check air sensor data if present
        air = sensor_data.get("air")
        if isinstance(air, dict):
            air_temp = air.get("temperature_celsius")
            if air_temp is not None:
                if not (-40.0 <= float(air_temp) <= 70.0):
                    return False, f"Air temperature out of bounds [-40 to +70°C]: {air_temp}"

            humidity = air.get("humidity_percent")
            if humidity is not None:
                if not (0.0 <= float(humidity) <= 100.0):
                    return False, f"Relative humidity out of bounds [0-100%]: {humidity}"

            rainfall = air.get("rainfall_mm")
            if rainfall is not None:
                if float(rainfall) < 0.0 or float(rainfall) > 500.0:
                    return False, f"Rainfall out of plausible bounds [0-500mm]: {rainfall}"

        return True, "Telemetry valid."

    def evaluate_safety_override(
        self,
        field_analysis_dict: Dict[str, Any],
        sensor_data: Optional[Dict[str, Any]],
        weather_data: Optional[Dict[str, Any]],
    ) -> Optional[DecisionResult]:
        """
        Evaluate overriding safety checks. Returns a DecisionResult if a safety check triggers,
        otherwise None.
        """
        rules_triggered: List[str] = []

        # 1. Telemetry validation check
        valid_telemetry, tele_err = self.validate_telemetry(sensor_data)
        if not valid_telemetry:
            rules_triggered.append("RULE_SAFETY_INVALID_TELEMETRY")
            return DecisionResult(
                action=ActionType.WARN,
                reason=f"Safety Block: Sensor telemetry invalid — {tele_err}",
                priority=PriorityLevel.CRITICAL,
                requires_confirmation=True,
                safety_status=SafetyStatus.TELEMETRY_INVALID,
                audit=DecisionAudit(
                    triggered_rules=rules_triggered,
                    inputs_considered={"sensor_data": sensor_data, "error": tele_err},
                ),
            )

        # 2. Check for missing / malformed field analysis
        if not field_analysis_dict or not isinstance(field_analysis_dict, dict):
            rules_triggered.append("RULE_SAFETY_MALFORMED_AI_OUTPUT")
            return DecisionResult(
                action=ActionType.WARN,
                reason="Safety Block: AI field analysis payload is missing or malformed.",
                priority=PriorityLevel.CRITICAL,
                requires_confirmation=True,
                safety_status=SafetyStatus.SAFETY_BLOCK,
                audit=DecisionAudit(
                    triggered_rules=rules_triggered,
                    inputs_considered={"field_analysis": field_analysis_dict},
                ),
            )

        # 3. Check for critical climate hazards (e.g. flood >= 0.80 or waterlogging >= 0.80)
        climate = field_analysis_dict.get("climate_risk") or {}
        if isinstance(climate, dict):
            flood_risk = float(climate.get("flood", 0.0))
            waterlog_risk = float(climate.get("waterlogging", 0.0))
            if (
                flood_risk >= self.settings.CRITICAL_CLIMATE_HAZARD_THRESHOLD
                or waterlog_risk >= self.settings.CRITICAL_CLIMATE_HAZARD_THRESHOLD
            ):
                rules_triggered.append("RULE_SAFETY_CRITICAL_CLIMATE_HAZARD")
                return DecisionResult(
                    action=ActionType.WARN,
                    reason=(
                        f"Safety Block: Critical environmental hazard detected "
                        f"(Flood risk: {flood_risk:.0%}, Waterlogging risk: {waterlog_risk:.0%}). "
                        "All automated operations blocked."
                    ),
                    priority=PriorityLevel.CRITICAL,
                    requires_confirmation=True,
                    safety_status=SafetyStatus.CLIMATE_HAZARD,
                    audit=DecisionAudit(
                        triggered_rules=rules_triggered,
                        inputs_considered={"climate_risk": climate},
                    ),
                )

        # 4. Check for contradictory conditions (e.g. soil moisture >= 90% but drought risk >= 0.80)
        if isinstance(sensor_data, dict) and "soil" in sensor_data:
            soil_moist = sensor_data["soil"].get("moisture_percent")
            drought_risk = climate.get("drought", 0.0) if isinstance(climate, dict) else 0.0
            if (
                soil_moist is not None
                and float(soil_moist) >= 90.0
                and float(drought_risk) >= 0.80
            ):
                rules_triggered.append("RULE_SAFETY_CONTRADICTORY_TELEMETRY")
                return DecisionResult(
                    action=ActionType.WARN,
                    reason=(
                        f"Safety Block: Contradictory inputs detected — soil moisture is {soil_moist}% "
                        f"while drought risk is {drought_risk:.0%}. Manual verification required."
                    ),
                    priority=PriorityLevel.HIGH,
                    requires_confirmation=True,
                    safety_status=SafetyStatus.SAFETY_BLOCK,
                    audit=DecisionAudit(
                        triggered_rules=rules_triggered,
                        inputs_considered={
                            "soil_moisture": soil_moist,
                            "drought_risk": drought_risk,
                        },
                    ),
                )

        return None
