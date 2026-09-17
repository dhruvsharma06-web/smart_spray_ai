import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.canonical import analyze_field
from app.db.sqlite import ActionHistoryModel, DecisionModel, DeviceModel, FieldModel, gen_id, get_sqlite_db
from app.iot.mock_service import mock_iot_service
from app.services.actuator_authorization import ActuatorAuthorizationService

logger = logging.getLogger("flutter-compat")
router = APIRouter(prefix="/api/v1", tags=["flutter-compat"])

class ManualSprayRequest(BaseModel):
    device_id: str = "device-001"
    duration_ms: int = 5000
    volume_ml: Optional[float] = 250.0
    command_id: Optional[str] = None
    decision_id: Optional[str] = None

class StopSprayRequest(BaseModel):
    device_id: str = "device-001"

class EmergencyStopRequest(BaseModel):
    device_id: str = "device-001"
    reason: str = "Emergency stop invoked via Flutter client"

# ==========================================
# 1. AI Detection Flutter Shape
# ==========================================

@router.post("/ai/detect")
async def flutter_ai_detect(
    file: UploadFile = File(...),
    crop_type: str = Form("Tomato"),
    field_id: str = Form("field-001"),
    device_id: str = Form("device-001"),
    demo_scenario: Optional[str] = Query(None),
    x_demo_scenario: Optional[str] = Header(None, alias="X-Demo-Scenario"),
    db: AsyncSession = Depends(get_sqlite_db),
):
    """
    Compatibility route for Flutter's POST /api/v1/ai/detect:
    Translates multipart 'file' -> 'image' and maps output into Flutter presentation structure.
    """
    raw_result = await analyze_field(
        image=file,
        field_id=field_id,
        sensor_data=None,
        weather_data=None,
        crop_stage="vegetative",
        explainer_mode="auto",
        demo_scenario=demo_scenario,
        x_demo_scenario=x_demo_scenario,
        db=db,
    )

    analysis = raw_result["analysis"]
    decision = raw_result["decision"]
    actuation = raw_result["actuation"]

    # Map disease / crop / severity for Flutter presentation
    disease = analysis.get("disease") or {}
    crop = analysis.get("crop") or {}
    severity = analysis.get("severity") or {}
    metadata = analysis.get("metadata") or {}

    flutter_presentation = {
        "success": True,
        "data": {
            "analysis_id": raw_result["analysis_id"],
            "crop": {
                "name": crop.get("name", crop_type),
                "confidence": crop.get("confidence", 0.95),
            },
            "disease": {
                "name": disease.get("name") if isinstance(disease, dict) else "Healthy",
                "confidence": disease.get("confidence", 0.90) if isinstance(disease, dict) else 0.90,
                "severity": severity.get("level", "LOW") if severity else "LOW",
                "affected_area_percent": severity.get("affected_area_percent", 0.0) if severity else 0.0,
            },
            "pests": analysis.get("pests", []),
            "severity": severity,
            "climate_risk": analysis.get("climate_risk", {}),
            "explanation": metadata.get("farmer_explanation", "AI crop health diagnosis completed."),
            "recommendations": metadata.get("treatment_recommendations", []),
        },
        "decision": {
            "decision_id": raw_result["decision_id"],
            "recommendation": decision.get("primary_decision", "MONITOR"),
            "risk_level": decision.get("risk_level", "LOW"),
            "actions": decision.get("actions", []),
            "warnings": decision.get("warnings", []),
            "auto_permitted": actuation.get("authorized", False),
            "actuation": actuation,
        },
    }
    return flutter_presentation

# ==========================================
# 2. Device Status Endpoint
# ==========================================

@router.get("/devices/{device_id}/status")
async def flutter_get_device_status(device_id: str):
    stat = mock_iot_service.get_status(device_id)
    return stat

# ==========================================
# 3. Spray Controls
# ==========================================

@router.post("/spray/manual")
async def flutter_manual_spray(
    payload: ManualSprayRequest,
    db: AsyncSession = Depends(get_sqlite_db),
):
    device_id = payload.device_id
    decision_id = payload.decision_id

    # If decision_id not provided by Flutter, look up the latest valid decision for this device's field
    if not decision_id:
        dev_res = await db.execute(select(DeviceModel).where(DeviceModel.id == device_id))
        dev = dev_res.scalar_one_or_none()
        field_id = dev.field_id if dev else "field-001"

        dec_stmt = (
            select(DecisionModel)
            .where(DecisionModel.field_id == field_id)
            .order_by(desc(DecisionModel.timestamp))
            .limit(1)
        )
        dec_res = await db.execute(dec_stmt)
        latest_dec = dec_res.scalar_one_or_none()
        if latest_dec:
            decision_id = latest_dec.id

    # Strictly validate against the single authoritative safety gate
    auth_res = await ActuatorAuthorizationService.authorize_action(
        db=db,
        device_id=device_id,
        action="SPRAY",
        decision_id=decision_id,
    )

    if not auth_res.authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "status": "REJECTED",
                "message": f"Safety boundary rejected manual spray: {auth_res.reason}",
            },
        )

    iot_res = mock_iot_service.spray(
        device_id=device_id,
        duration_ms=payload.duration_ms,
        volume_ml=payload.volume_ml or 250.0,
    )

    # Log action history
    act_id = payload.command_id or gen_id("cmd-")
    act_entry = ActionHistoryModel(
        id=act_id,
        field_id=auth_res.field_id or "field-001",
        device_id=device_id,
        decision_id=decision_id,
        action="SPRAY",
        status=iot_res["status"],
        duration_ms=payload.duration_ms,
        volume_ml=payload.volume_ml,
        message=iot_res["message"],
    )
    db.add(act_entry)
    await db.commit()

    return {
        "success": True,
        "status": "SUCCESS",
        "command_id": act_id,
        "device_id": device_id,
        "iot_result": iot_res,
    }

@router.post("/spray/stop")
async def flutter_stop_spray(payload: StopSprayRequest, db: AsyncSession = Depends(get_sqlite_db)):
    iot_res = mock_iot_service.stop(payload.device_id)
    act_entry = ActionHistoryModel(
        id=gen_id("cmd-"),
        field_id="field-001",
        device_id=payload.device_id,
        decision_id=None,
        action="STOP",
        status="STOPPED",
        message=iot_res["message"],
    )
    db.add(act_entry)
    await db.commit()
    return {"success": True, "status": "STOPPED", "device_id": payload.device_id}

@router.post("/spray/emergency-stop")
async def flutter_emergency_stop(payload: EmergencyStopRequest, db: AsyncSession = Depends(get_sqlite_db)):
    iot_res = mock_iot_service.emergency_stop(payload.device_id, reason=payload.reason)
    act_entry = ActionHistoryModel(
        id=gen_id("cmd-"),
        field_id="field-001",
        device_id=payload.device_id,
        decision_id=None,
        action="EMERGENCY_STOP",
        status="EMERGENCY_HALTED",
        message=payload.reason,
    )
    db.add(act_entry)
    await db.commit()
    return {"success": True, "status": "EMERGENCY_HALTED", "device_id": payload.device_id, "reason": payload.reason}

@router.post("/spray/reset-emergency-stop")
async def flutter_reset_emergency_stop(payload: StopSprayRequest):
    iot_res = mock_iot_service.reset_emergency_stop(payload.device_id)
    return {"success": True, "status": "ONLINE", "device_id": payload.device_id}

@router.get("/spray/history")
async def flutter_spray_history(
    device_id: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_sqlite_db),
):
    stmt = select(ActionHistoryModel).order_by(desc(ActionHistoryModel.timestamp)).limit(limit)
    if device_id:
        stmt = stmt.where(ActionHistoryModel.device_id == device_id)
    res = await db.execute(stmt)
    records = res.scalars().all()
    return [
        {
            "id": r.id,
            "device_id": r.device_id,
            "decision_id": r.decision_id,
            "timestamp": r.timestamp.isoformat(),
            "action": r.action,
            "status": r.status,
            "duration_ms": r.duration_ms or 0,
            "volume_ml": r.volume_ml or 0.0,
            "message": r.message,
        }
        for r in records
    ]

# ==========================================
# 4. WebSocket Live Telemetry Stream
# ==========================================

@router.websocket("/ws/{device_id}")
async def websocket_device_stream(websocket: WebSocket, device_id: str):
    await websocket.accept()
    logger.info(f"WebSocket client connected for device '{device_id}'")
    try:
        while True:
            # Emit telemetry frame every 3 seconds for Flutter dashboard live charts
            stat = mock_iot_service.get_status(device_id)
            frame = {
                "type": "TELEMETRY",
                "device_id": device_id,
                "payload": {
                    "soil_moisture": 28.5,
                    "soil_temperature": 24.0,
                    "air_temperature": 26.5,
                    "humidity": 62.0,
                    "battery": stat["battery"],
                    "tank_level": stat["tank_level"],
                    "current_action": stat["current_action"],
                    "status": stat["status"],
                },
            }
            await websocket.send_text(json.dumps(frame))
            await asyncio.sleep(3.0)
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected for device '{device_id}'")
    except Exception as e:
        logger.error(f"WebSocket error for device '{device_id}': {e}")
