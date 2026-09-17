from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models import Device, SprayEvent, Decision

ALLOWED = {"spray", "irrigate", "stop"}

def validate_command(device: Device, action: str, decision: dict | None = None):
    if action not in ALLOWED: raise HTTPException(400, "Unsupported command")
    if action != "stop" and device.status == "OFFLINE": raise HTTPException(409, "Device is offline")
    if action == "spray":
        if not decision: raise HTTPException(409, "Spray requires an approved decision")
        if decision.get("primary_decision") != "SPRAY": raise HTTPException(409, "Decision engine has not authorized spraying")
        if decision.get("requires_confirmation"): raise HTTPException(409, "Decision requires confirmation")
        if decision.get("risk_level") == "CRITICAL": raise HTTPException(409, "Critical risk blocks spraying")
    if action == "irrigate":
        if not decision: raise HTTPException(409, "Irrigation requires an approved decision")
        if decision.get("primary_decision") != "IRRIGATE": raise HTTPException(409, "Decision engine has not authorized irrigation")
        if decision.get("requires_confirmation"): raise HTTPException(409, "Decision requires confirmation")
    if action in {"spray", "irrigate"} and device.tank_level is not None and device.tank_level <= 5: raise HTTPException(409, "Tank level too low")

def execute_local(db: Session, device: Device, action: str, decision_id: int | None = None):
    now = datetime.now(timezone.utc)
    if action == "stop": device.pump_active = False
    else: device.pump_active = True
    device.last_command_at = now
    event = SprayEvent(device_id=device.id, decision_id=decision_id, action=action.upper(), status="STARTED" if action != "stop" else "STOPPED", started_at=now if action != "stop" else None, completed_at=now if action == "stop" else None)
    db.add(event)
    return event
