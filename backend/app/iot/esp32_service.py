import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx
from app.config import settings

logger = logging.getLogger("esp32-service")

# Centralized configurable telemetry timeout (in seconds)
TELEMETRY_TIMEOUT_SECONDS: int = 10

class ESP32Service:
    """
    ESP32 HTTP Command Bridge and Telemetry Service.
    Supports HTTP polling, telemetry timeout tracking, and direct HTTP dispatch to ESP32 hardware.
    Physical connectivity is determined STRICTLY from recent telemetry / ACK activity within
    TELEMETRY_TIMEOUT_SECONDS.
    """

    def __init__(self, base_url: Optional[str] = None):
        self._base_url = base_url
        # In-memory command queue: device_id -> list of command dicts
        self._command_queues: Dict[str, List[Dict[str, Any]]] = {}
        # In-memory device states & telemetry
        self._states: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    @property
    def base_url(self) -> str:
        url = self._base_url or getattr(settings, "esp32_base_url", "http://192.168.1.50")
        return url.rstrip("/")

    def _get_or_init_state(self, device_id: str) -> Dict[str, Any]:
        if device_id not in self._states:
            self._states[device_id] = {
                "device_id": device_id,
                "status": "OFFLINE",
                "current_action": "IDLE",
                "pump_status": "off",
                "esp32_connected": False,
                "emergency_halted": False,
                "last_seen": None,
                "last_telemetry_at": None,
                "soil": None,
                "environment": None,
            }
        return self._states[device_id]

    async def send_command(self, device_id: str, command: str, duration_ms: int = 5000) -> Dict[str, Any]:
        """
        Directly send HTTP POST command to physical ESP32 at POST {ESP32_BASE_URL}/command
        """
        url = f"{self.base_url}/command"
        payload = {
            "command": command.upper(),
            "duration_ms": duration_ms,
        }
        logger.info(f"Direct push sending to ESP32 ({url}): {payload}")
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code in (200, 201):
                    return {"success": True, "status": "DISPATCHED", "data": res.json()}
                return {"success": False, "status": "ERROR", "error": f"ESP32 HTTP {res.status_code}"}
        except Exception as e:
            logger.warning(f"Direct HTTP push to ESP32 failed ({url}): {e}")
            return {"success": False, "status": "UNREACHABLE", "error": str(e)}

    async def queue_command(self, device_id: str, command: str, duration_ms: int = 5000) -> Dict[str, Any]:
        """
        Queue command for ESP32 polling.
        Commands: SPRAY, IRRIGATE, STOP, EMERGENCY_STOP, RESET
        """
        cmd_upper = command.upper()
        state = self._get_or_init_state(device_id)

        if cmd_upper == "EMERGENCY_STOP":
            state["emergency_halted"] = True
            state["current_action"] = "EMERGENCY_HALTED"
            state["status"] = "ERROR"
            state["pump_status"] = "off"
        elif cmd_upper in ("RESET", "RESET_EMERGENCY_STOP"):
            state["emergency_halted"] = False
            state["current_action"] = "IDLE"
            state["status"] = "ONLINE" if state.get("last_telemetry_at") else "OFFLINE"
            cmd_upper = "RESET"
        elif state.get("emergency_halted"):
            return {
                "success": False,
                "status": "REJECTED",
                "message": f"Device {device_id} is in EMERGENCY_HALTED state",
            }

        item = {
            "command": cmd_upper,
            "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        async with self._lock:
            if device_id not in self._command_queues:
                self._command_queues[device_id] = []
            self._command_queues[device_id].append(item)

        logger.info(f"Queued command '{cmd_upper}' for device '{device_id}'")
        return {
            "success": True,
            "status": "QUEUED",
            "device_id": device_id,
            "command": cmd_upper,
            "duration_ms": duration_ms,
            "is_real_hardware": True,
        }

    async def get_pending_command(self, device_id: str) -> Dict[str, Any]:
        """
        Pops and returns the pending command for device_id.
        Consumed only once. Returns {"command": "NONE"} if empty.
        """
        async with self._lock:
            queue = self._command_queues.get(device_id, [])
            if queue:
                item = queue.pop(0)
                return {
                    "command": item["command"],
                    "duration_ms": item.get("duration_ms", 5000),
                }
            return {"command": "NONE"}

    async def record_ack(self, device_id: str, command: str, status_str: str) -> Dict[str, Any]:
        """
        Record ESP32 ack response:
        {"command": "SPRAY", "status": "STARTED|COMPLETED"}
        """
        state = self._get_or_init_state(device_id)
        now = datetime.now(timezone.utc)
        state["last_telemetry_at"] = now
        state["last_seen"] = now.isoformat()
        state["esp32_connected"] = True
        cmd_upper = command.upper()
        stat_upper = status_str.upper()

        if stat_upper == "STARTED":
            if cmd_upper == "SPRAY":
                state["current_action"] = "SPRAYING"
                state["pump_status"] = "on"
            elif cmd_upper == "IRRIGATE":
                state["current_action"] = "IRRIGATING"
                state["pump_status"] = "on"
        elif stat_upper in ("COMPLETED", "STOPPED", "FINISHED"):
            state["current_action"] = "IDLE"
            state["pump_status"] = "off"
        elif stat_upper == "EMERGENCY_HALTED":
            state["current_action"] = "EMERGENCY_HALTED"
            state["emergency_halted"] = True
            state["pump_status"] = "off"

        state["status"] = "ONLINE" if not state.get("emergency_halted") else "ERROR"

        logger.info(f"Device '{device_id}' ack recorded: {cmd_upper} -> {stat_upper}")

        # Real Actuation Notifications & Action History Lifecycle updates
        try:
            from app.db.sqlite import AsyncSessionLocal, ActionHistoryModel
            from app.services.notification_service import NotificationService
            from sqlalchemy import select, desc

            async with AsyncSessionLocal() as session:
                stmt = (
                    select(ActionHistoryModel)
                    .where(ActionHistoryModel.device_id == device_id)
                    .order_by(desc(ActionHistoryModel.timestamp))
                    .limit(1)
                )
                res = await session.execute(stmt)
                latest_act = res.scalar_one_or_none()

                field_id = latest_act.field_id if latest_act else "field-001"
                dec_id = latest_act.decision_id if latest_act else None
                act_id = latest_act.id if latest_act else None
                duration_sec = (latest_act.duration_ms // 1000) if (latest_act and latest_act.duration_ms) else 5
                plants_targeted = latest_act.plants_targeted if latest_act else None
                disease = latest_act.disease if latest_act else None

                if stat_upper == "STARTED":
                    if latest_act:
                        latest_act.status = "STARTED"
                        latest_act.ack_state = "STARTED"

                    notif_type = f"{cmd_upper}_STARTED"
                    op_title = "Spray Started" if cmd_upper == "SPRAY" else "Irrigation Started"
                    op_msg = f"{cmd_upper.capitalize()} operation active on {device_id}."
                    if plants_targeted:
                        op_msg += f" {plants_targeted} plants targeted · {duration_sec}s."

                    await NotificationService.create_notification(
                        db=session,
                        notification_type=notif_type,
                        title=op_title,
                        message=op_msg,
                        severity="INFO",
                        source="ESP32_ACTUATOR",
                        device_id=device_id,
                        field_id=field_id,
                        decision_id=dec_id,
                        action_id=act_id,
                        stats={
                            "command": cmd_upper,
                            "status": "STARTED",
                            "duration_seconds": duration_sec,
                            "plants_targeted": plants_targeted,
                        },
                        deduplicate=False,
                    )
                    await session.commit()

                elif stat_upper in ("COMPLETED", "FINISHED"):
                    if latest_act:
                        latest_act.status = "COMPLETED"
                        latest_act.ack_state = "COMPLETED"

                    notif_type = f"{cmd_upper}_COMPLETED"
                    op_title = "Spray Completed" if cmd_upper == "SPRAY" else "Irrigation Completed"
                    target_str = f" {plants_targeted} plants targeted ·" if plants_targeted else ""
                    treat_str = f" {disease} treatment cycle completed." if disease else f" {cmd_upper.capitalize()} cycle completed."
                    op_msg = f"{treat_str.strip()}{target_str} {duration_sec}s."

                    await NotificationService.create_notification(
                        db=session,
                        notification_type=notif_type,
                        title=op_title,
                        message=op_msg,
                        severity="INFO",
                        source="ESP32_ACTUATOR",
                        device_id=device_id,
                        field_id=field_id,
                        decision_id=dec_id,
                        action_id=act_id,
                        stats={
                            "command": cmd_upper,
                            "status": "COMPLETED",
                            "duration_seconds": duration_sec,
                            "plants_targeted": plants_targeted,
                            "disease": disease,
                        },
                        deduplicate=False,
                    )
                    await session.commit()
        except Exception as e:
            logger.warning(f"Failed to record ack notification / action history update: {e}")

        return {"success": True}

    def update_telemetry(self, device_id: str, telemetry: Dict[str, Any]) -> None:
        """
        Update state from incoming telemetry (heartbeat every 3s).
        """
        state = self._get_or_init_state(device_id)
        now = datetime.now(timezone.utc)
        state["last_telemetry_at"] = now
        state["last_seen"] = now.isoformat()
        state["esp32_connected"] = True

        if "pump" in telemetry and telemetry["pump"] is not None:
            state["pump_status"] = "on" if telemetry["pump"] else "off"
            if telemetry["pump"] and state["current_action"] == "IDLE":
                state["current_action"] = "SPRAYING"
            elif not telemetry["pump"] and not state["emergency_halted"] and state["current_action"] in ("SPRAYING", "IRRIGATING"):
                state["current_action"] = "IDLE"

        if "soil" in telemetry and isinstance(telemetry["soil"], dict):
            state["soil"] = telemetry["soil"]
        if "environment" in telemetry and isinstance(telemetry["environment"], dict):
            state["environment"] = telemetry["environment"]

    def get_status(self, device_id: str) -> Dict[str, Any]:
        """
        Return unified device status for Flutter & Backend.
        Physical connectivity is evaluated strictly based on TELEMETRY_TIMEOUT_SECONDS (10s).
        """
        state = self._get_or_init_state(device_id)
        last_tel = state.get("last_telemetry_at")
        now = datetime.now(timezone.utc)

        is_connected = False
        if last_tel is not None:
            if (now - last_tel).total_seconds() <= TELEMETRY_TIMEOUT_SECONDS:
                is_connected = True

        emergency_halted = state.get("emergency_halted", False)

        if not is_connected:
            status = "ERROR" if emergency_halted else "OFFLINE"
            current_action = "EMERGENCY_HALTED" if emergency_halted else "IDLE"
            pump_status = "off"
            soil = None
            environment = None
        else:
            status = "ERROR" if emergency_halted else "ONLINE"
            current_action = state.get("current_action", "IDLE")
            pump_status = state.get("pump_status", "off")
            soil = state.get("soil")
            environment = state.get("environment")

        return {
            "device_id": device_id,
            "status": status,
            "pump_status": pump_status,
            "current_action": current_action,
            "esp32_connected": is_connected,
            "last_seen": state["last_seen"],
            "mode": "ASSISTED",
            "soil": soil,
            "environment": environment,
        }

esp32_service = ESP32Service()
