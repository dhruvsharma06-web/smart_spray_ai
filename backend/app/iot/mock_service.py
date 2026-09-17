import logging
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger("mock-iot")

class MockIoTService:
    """
    Mock IoT actuator abstraction for Smart Spray prototype.
    Simulates hardware actions (spray nozzles, irrigation solenoids, emergency cutoffs)
    without physical GPIO or serial communication.
    Explicitly flags all operational outcomes as SIMULATED.
    """

    def __init__(self):
        # In-memory device state cache for rapid simulation updates
        self._states: Dict[str, Dict[str, Any]] = {}

    def _get_or_init_state(self, device_id: str) -> Dict[str, Any]:
        if device_id not in self._states:
            self._states[device_id] = {
                "device_id": device_id,
                "status": "ONLINE",
                "battery": 95,
                "tank_level": 88,
                "current_action": "IDLE",
                "emergency_halted": False,
                "last_seen": datetime.now(timezone.utc).isoformat(),
            }
        return self._states[device_id]

    def spray(
        self,
        device_id: str,
        duration_ms: int = 5000,
        volume_ml: float = 250.0,
    ) -> Dict[str, Any]:
        state = self._get_or_init_state(device_id)
        if state["emergency_halted"]:
            raise RuntimeError(f"Device {device_id} is in EMERGENCY_HALTED state. Cannot actuate.")
        
        state["current_action"] = "SPRAYING"
        # Simulate slight tank depletion
        state["tank_level"] = max(5, state["tank_level"] - 2)
        state["last_seen"] = datetime.now(timezone.utc).isoformat()
        
        logger.info(
            f"[MOCK IoT] Device '{device_id}' SIMULATED SPRAY: duration={duration_ms}ms, volume={volume_ml}ml"
        )
        return {
            "authorized": True,
            "executed": True,
            "status": "SIMULATED",
            "action": "SPRAY",
            "device_id": device_id,
            "duration_ms": duration_ms,
            "volume_ml": volume_ml,
            "is_real_hardware": False,
            "message": "Simulated spray nozzle cycle executed successfully on Mock IoT adapter",
        }

    def irrigate(
        self,
        device_id: str,
        duration_ms: int = 10000,
    ) -> Dict[str, Any]:
        state = self._get_or_init_state(device_id)
        if state["emergency_halted"]:
            raise RuntimeError(f"Device {device_id} is in EMERGENCY_HALTED state. Cannot actuate.")
        
        state["current_action"] = "IRRIGATING"
        state["last_seen"] = datetime.now(timezone.utc).isoformat()
        
        logger.info(f"[MOCK IoT] Device '{device_id}' SIMULATED IRRIGATION: duration={duration_ms}ms")
        return {
            "authorized": True,
            "executed": True,
            "status": "SIMULATED",
            "action": "IRRIGATE",
            "device_id": device_id,
            "duration_ms": duration_ms,
            "is_real_hardware": False,
            "message": "Simulated irrigation solenoid valve opened on Mock IoT adapter",
        }

    def stop(self, device_id: str) -> Dict[str, Any]:
        state = self._get_or_init_state(device_id)
        state["current_action"] = "IDLE"
        state["last_seen"] = datetime.now(timezone.utc).isoformat()
        
        logger.info(f"[MOCK IoT] Device '{device_id}' STOPPED")
        return {
            "authorized": True,
            "executed": True,
            "status": "STOPPED",
            "action": "STOP",
            "device_id": device_id,
            "is_real_hardware": False,
            "message": "Simulated actuators halted to safe idle state",
        }

    def emergency_stop(self, device_id: str, reason: str = "Emergency stop requested") -> Dict[str, Any]:
        state = self._get_or_init_state(device_id)
        state["current_action"] = "EMERGENCY_HALTED"
        state["status"] = "ERROR"
        state["emergency_halted"] = True
        state["last_seen"] = datetime.now(timezone.utc).isoformat()
        
        logger.warning(f"[MOCK IoT] Device '{device_id}' EMERGENCY STOP TRIGGERED: reason='{reason}'")
        return {
            "authorized": True,
            "executed": True,
            "status": "EMERGENCY_HALTED",
            "action": "EMERGENCY_STOP",
            "device_id": device_id,
            "reason": reason,
            "is_real_hardware": False,
            "message": "Emergency cutoff engaged: power isolated and actuators locked",
        }

    def reset_emergency_stop(self, device_id: str) -> Dict[str, Any]:
        state = self._get_or_init_state(device_id)
        state["current_action"] = "IDLE"
        state["status"] = "ONLINE"
        state["emergency_halted"] = False
        state["last_seen"] = datetime.now(timezone.utc).isoformat()
        
        logger.info(f"[MOCK IoT] Device '{device_id}' EMERGENCY STOP RESET")
        return {
            "authorized": True,
            "executed": True,
            "status": "ONLINE",
            "action": "RESET_EMERGENCY_STOP",
            "device_id": device_id,
            "is_real_hardware": False,
            "message": "Emergency lock cleared; device restored to ONLINE state",
        }

    def get_status(self, device_id: str) -> Dict[str, Any]:
        state = self._get_or_init_state(device_id)
        return {
            "device_id": device_id,
            "status": state["status"],
            "battery": state["battery"],
            "tank_level": state["tank_level"],
            "current_action": state["current_action"],
            "last_seen": state["last_seen"],
            "pump_status": "on" if state["current_action"] in ("SPRAYING", "IRRIGATING") else "off",
            "esp32_connected": not state["emergency_halted"],
            "mode": "ASSISTED",
        }

# Global singleton mock IoT service
mock_iot_service = MockIoTService()
