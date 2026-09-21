import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.canonical import analyze_field
from app.db.sqlite import ActionHistoryModel, DecisionModel, DeviceModel, FieldModel, NotificationModel, gen_id, get_sqlite_db
from app.iot.esp32_service import esp32_service
from app.services.actuator_authorization import ActuatorAuthorizationService
from app.services.notification_service import NotificationService

logger = logging.getLogger("flutter-compat")
router = APIRouter(prefix="/api/v1", tags=["flutter-compat"])
ws_router = APIRouter(tags=["flutter-ws"])

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

class ESP32AckRequest(BaseModel):
    command: str
    status: str

class ESP32CommandQueueRequest(BaseModel):
    command: str
    duration_ms: Optional[int] = 5000

# ==========================================
# 1. AI Status & Detection Flutter Shape
# ==========================================

@router.get("/ai/status")
async def flutter_get_ai_status():
    return {
        "success": True,
        "data": {
            "ready": True,
            "status": "ONLINE",
            "model_version": "1.0.0",
        },
    }

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

    disease_name = disease.get("name") if isinstance(disease, dict) else (disease or "healthy")
    if not disease_name:
        disease_name = "healthy"
    disease_conf = disease.get("confidence", 0.90) if isinstance(disease, dict) else 0.90

    crop_name = crop.get("name", crop_type) if isinstance(crop, dict) else (crop or crop_type)
    crop_conf = crop.get("confidence", 0.95) if isinstance(crop, dict) else 0.95

    sev_pct = severity.get("affected_area_percent", 0.0) if isinstance(severity, dict) else 0.0
    sev_lvl = severity.get("level", "LOW") if isinstance(severity, dict) else "LOW"
    is_uncertain = str(disease_name).lower() in ("low_confidence", "uncertain") or disease_conf < 0.60

    flutter_data = {
        "analysis_id": raw_result["analysis_id"],
        "crop": {
            "name": crop_name,
            "confidence": crop_conf,
        },
        "disease": str(disease_name),
        "uncertain": is_uncertain,
        "leaf": {
            "detected": True,
        },
        "lesion": {
            "confidence": disease_conf,
        },
        "severity": {
            "percentage": sev_pct,
            "level": sev_lvl,
            "affected_area_percent": sev_pct,
        },
        "pests": analysis.get("pests", []),
        "climate_risk": analysis.get("climate_risk", {}),
        "explanation": metadata.get("farmer_explanation", "AI crop health diagnosis completed."),
        "recommendations": metadata.get("treatment_recommendations", []),
    }

    flutter_decision = {
        "decision_id": raw_result["decision_id"],
        "recommendation": decision.get("primary_decision", "MONITOR"),
        "risk_level": decision.get("risk_level", "LOW"),
        "actions": decision.get("actions", []),
        "warnings": decision.get("warnings", []),
        "auto_permitted": actuation.get("authorized", False),
        "actuation": actuation,
    }

    # Satisfies both test_21 (expects data.disease, data.crop, decision)
    # and Flutter ai_repository.dart unwrapping (expects body['data'] to contain data, decision)
    inner_payload = {
        "success": True,
        "disease": str(disease_name),
        "crop": {
            "name": crop_name,
            "confidence": crop_conf,
        },
        "data": flutter_data,
        "decision": flutter_decision,
    }

    # Trigger Climate Warnings & Disease Detected Alert
    try:
        telemetry = esp32_service.get_status(device_id)
        # 1. Climate Alerts
        await NotificationService.generate_climate_alerts(
            db=db,
            field_id=field_id,
            device_id=device_id,
            analysis=analysis,
            sensor_data=telemetry if (telemetry and telemetry.get("esp32_connected")) else None,
            weather_data=None,
        )

        # 2. Disease Detected Alert
        dis_str = str(disease_name)
        if dis_str and dis_str.lower() != "healthy" and crop_conf >= 0.5:
            await NotificationService.create_notification(
                db=db,
                notification_type="DISEASE_DETECTED",
                title="Disease Detected",
                message=f"Possible {dis_str.replace('_', ' ')} detected on {crop_name}.",
                severity="HIGH" if crop_conf >= 0.8 else "MEDIUM",
                source="AI_DETECTION",
                device_id=device_id,
                field_id=field_id,
                decision_id=raw_result.get("decision_id"),
                stats={
                    "disease": dis_str,
                    "confidence": crop_conf,
                    "crop": crop_name,
                    "severity": sev_lvl,
                    "affected_percentage": sev_pct,
                },
                deduplicate=True,
            )

        # 3. Delayed Action Alert if Decision Engine returned DELAY
        prim_dec = str(decision.get("primary_decision", "")).upper()
        if "DELAY" in prim_dec:
            await NotificationService.create_notification(
                db=db,
                notification_type="SPRAY_DELAYED",
                title="Spray Delayed",
                message="Spraying delayed by Decision Engine: rainfall or adverse weather conditions detected.",
                severity="MEDIUM",
                source="DECISION_ENGINE",
                device_id=device_id,
                field_id=field_id,
                decision_id=raw_result.get("decision_id"),
                deduplicate=True,
            )
        await db.commit()
    except Exception as ne:
        logger.warning(f"Failed to generate analysis notifications: {ne}")

    return {
        "success": True,
        "data": inner_payload,
        "decision": flutter_decision,
    }

# ==========================================
# 2. ESP32 Real Hardware IoT Bridge & Polling Endpoints
# ==========================================

@router.get("/iot/{device_id}/command")
async def get_iot_pending_command(device_id: str):
    return await esp32_service.get_pending_command(device_id)

@router.post("/iot/{device_id}/ack")
async def post_iot_ack(device_id: str, payload: ESP32AckRequest):
    await esp32_service.record_ack(device_id, payload.command, payload.status)
    return {"success": True}

@router.post("/iot/{device_id}/command")
async def post_iot_queue_command(device_id: str, payload: ESP32CommandQueueRequest):
    res = await esp32_service.queue_command(
        device_id=device_id,
        command=payload.command,
        duration_ms=payload.duration_ms or 5000,
    )
    return res

@router.get("/devices/{device_id}/status")
async def flutter_get_device_status(device_id: str):
    stat = esp32_service.get_status(device_id)
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

    # If decision_id not provided by Flutter, create a legitimate short-lived MANUAL_OPERATOR decision
    if not decision_id:
        manual_dec = await ActuatorAuthorizationService.create_manual_operator_decision(
            db=db,
            device_id=device_id,
            action="SPRAY",
            duration_ms=payload.duration_ms,
            ttl_seconds=60,
        )
        decision_id = manual_dec.id

    # Strictly validate against the single authoritative safety gate
    auth_res = await ActuatorAuthorizationService.authorize_action(
        db=db,
        device_id=device_id,
        action="SPRAY",
        decision_id=decision_id,
        duration_ms=payload.duration_ms,
        require_device_online=True,
    )

    if not auth_res.authorized:
        # Record blocked notification & action history
        try:
            from app.services.notification_service import NotificationService
            await NotificationService.create_notification(
                db=db,
                notification_type="SPRAY_BLOCKED",
                title="Spray Blocked",
                message=f"Safety boundary rejected manual spray: {auth_res.reason}",
                severity="HIGH",
                source="SAFETY_GATE",
                device_id=device_id,
                field_id=auth_res.field_id or "field-001",
                decision_id=decision_id,
                deduplicate=False,
            )
            act_entry = ActionHistoryModel(
                id=payload.command_id or gen_id("cmd-"),
                field_id=auth_res.field_id or "field-001",
                device_id=device_id,
                decision_id=decision_id,
                action="SPRAY",
                status="BLOCKED",
                duration_ms=payload.duration_ms,
                volume_ml=payload.volume_ml,
                message=f"Blocked: {auth_res.reason}",
                reason=auth_res.reason,
            )
            db.add(act_entry)
            await db.commit()
        except Exception:
            pass

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "status": "REJECTED",
                "message": f"Safety boundary rejected manual spray: {auth_res.reason}",
            },
        )

    # Queue real ESP32 command
    iot_res = await esp32_service.queue_command(
        device_id=device_id,
        command="SPRAY",
        duration_ms=payload.duration_ms,
    )

    # Log action history
    act_id = payload.command_id or gen_id("cmd-")
    act_entry = ActionHistoryModel(
        id=act_id,
        field_id=auth_res.field_id or "field-001",
        device_id=device_id,
        decision_id=decision_id,
        action="SPRAY",
        status="QUEUED",
        duration_ms=payload.duration_ms,
        volume_ml=payload.volume_ml,
        plants_targeted=None,
        message="Queued spray command for ESP32 real hardware bridge",
        reason="Manual operator spray authorized by safety boundary",
    )
    db.add(act_entry)

    # Record QUEUED notification
    try:
        from app.services.notification_service import NotificationService
        await NotificationService.create_notification(
            db=db,
            notification_type="SPRAY_QUEUED",
            title="Spray Queued",
            message=f"Spray command ({payload.duration_ms // 1000}s) queued for {device_id}. Awaiting ESP32 poll...",
            severity="INFO",
            source="MANUAL_OPERATOR",
            device_id=device_id,
            field_id=auth_res.field_id or "field-001",
            decision_id=decision_id,
            action_id=act_id,
            stats={"duration_seconds": payload.duration_ms // 1000},
            deduplicate=False,
        )
    except Exception:
        pass

    await db.commit()

    return {
        "success": True,
        "status": "QUEUED",
        "device_id": device_id,
        "command_id": act_id,
        "is_real_hardware": True,
    }

@router.post("/spray/irrigate")
async def flutter_irrigate(
    payload: ManualSprayRequest,
    db: AsyncSession = Depends(get_sqlite_db),
):
    device_id = payload.device_id
    decision_id = payload.decision_id

    if not decision_id:
        manual_dec = await ActuatorAuthorizationService.create_manual_operator_decision(
            db=db,
            device_id=device_id,
            action="IRRIGATE",
            duration_ms=payload.duration_ms,
            ttl_seconds=60,
        )
        decision_id = manual_dec.id

    auth_res = await ActuatorAuthorizationService.authorize_action(
        db=db,
        device_id=device_id,
        action="IRRIGATE",
        decision_id=decision_id,
        duration_ms=payload.duration_ms,
        require_device_online=True,
    )

    if not auth_res.authorized:
        # Record blocked notification & action history
        try:
            from app.services.notification_service import NotificationService
            await NotificationService.create_notification(
                db=db,
                notification_type="IRRIGATION_BLOCKED",
                title="Irrigation Blocked",
                message=f"Safety boundary rejected manual irrigation: {auth_res.reason}",
                severity="HIGH",
                source="SAFETY_GATE",
                device_id=device_id,
                field_id=auth_res.field_id or "field-001",
                decision_id=decision_id,
                deduplicate=False,
            )
            act_entry = ActionHistoryModel(
                id=payload.command_id or gen_id("cmd-"),
                field_id=auth_res.field_id or "field-001",
                device_id=device_id,
                decision_id=decision_id,
                action="IRRIGATE",
                status="BLOCKED",
                duration_ms=payload.duration_ms,
                volume_ml=payload.volume_ml,
                message=f"Blocked: {auth_res.reason}",
                reason=auth_res.reason,
            )
            db.add(act_entry)
            await db.commit()
        except Exception:
            pass

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "status": "REJECTED",
                "message": f"Safety boundary rejected manual irrigation: {auth_res.reason}",
            },
        )

    iot_res = await esp32_service.queue_command(
        device_id=device_id,
        command="IRRIGATE",
        duration_ms=payload.duration_ms,
    )

    act_id = payload.command_id or gen_id("cmd-")
    act_entry = ActionHistoryModel(
        id=act_id,
        field_id=auth_res.field_id or "field-001",
        device_id=device_id,
        decision_id=decision_id,
        action="IRRIGATE",
        status="QUEUED",
        duration_ms=payload.duration_ms,
        volume_ml=payload.volume_ml,
        plants_targeted=None,
        message="Queued irrigation command for ESP32 real hardware bridge",
        reason="Manual operator irrigation authorized by safety boundary",
    )
    db.add(act_entry)

    # Record QUEUED notification
    try:
        from app.services.notification_service import NotificationService
        await NotificationService.create_notification(
            db=db,
            notification_type="IRRIGATION_QUEUED",
            title="Irrigation Queued",
            message=f"Irrigation command ({payload.duration_ms // 1000}s) queued for {device_id}. Awaiting ESP32 poll...",
            severity="INFO",
            source="MANUAL_OPERATOR",
            device_id=device_id,
            field_id=auth_res.field_id or "field-001",
            decision_id=decision_id,
            action_id=act_id,
            stats={"duration_seconds": payload.duration_ms // 1000},
            deduplicate=False,
        )
    except Exception:
        pass

    await db.commit()

    return {
        "success": True,
        "status": "QUEUED",
        "device_id": device_id,
        "command_id": act_id,
        "is_real_hardware": True,
    }

@router.post("/spray/stop")
async def flutter_stop_spray(
    payload: Optional[StopSprayRequest] = None,
    db: AsyncSession = Depends(get_sqlite_db),
):
    req = payload or StopSprayRequest()
    await esp32_service.queue_command(req.device_id, "STOP")

    act_entry = ActionHistoryModel(
        id=gen_id("cmd-"),
        field_id="field-001",
        device_id=req.device_id,
        decision_id=None,
        action="STOP",
        status="STOPPED",
        duration_ms=0,
        volume_ml=0.0,
        message="Queued STOP command for ESP32 hardware bridge",
    )
    db.add(act_entry)
    await db.commit()
    return {"success": True, "status": "STOPPED", "device_id": req.device_id, "is_real_hardware": True}

@router.post("/spray/emergency-stop")
async def flutter_emergency_stop(
    payload: Optional[EmergencyStopRequest] = None,
    db: AsyncSession = Depends(get_sqlite_db),
):
    req = payload or EmergencyStopRequest()
    await esp32_service.queue_command(req.device_id, "EMERGENCY_STOP")

    act_entry = ActionHistoryModel(
        id=gen_id("cmd-"),
        field_id="field-001",
        device_id=req.device_id,
        decision_id=None,
        action="EMERGENCY_STOP",
        status="EMERGENCY_HALTED",
        duration_ms=0,
        volume_ml=0.0,
        message=req.reason,
    )
    db.add(act_entry)
    await db.commit()
    return {"success": True, "status": "EMERGENCY_HALTED", "device_id": req.device_id, "reason": req.reason, "is_real_hardware": True}

@router.post("/spray/reset-emergency-stop")
async def flutter_reset_emergency_stop(
    payload: Optional[StopSprayRequest] = None,
    db: AsyncSession = Depends(get_sqlite_db),
):
    req = payload or StopSprayRequest()
    await esp32_service.queue_command(req.device_id, "RESET")

    act_entry = ActionHistoryModel(
        id=gen_id("cmd-"),
        field_id="field-001",
        device_id=req.device_id,
        decision_id=None,
        action="RESET_EMERGENCY_STOP",
        status="ONLINE",
        duration_ms=0,
        volume_ml=0.0,
        message="Emergency stop cleared by operator",
    )
    db.add(act_entry)
    await db.commit()
    return {"success": True, "status": "ONLINE", "device_id": req.device_id, "is_real_hardware": True}

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
            "command_id": r.id,
            "device_id": r.device_id,
            "decision_id": r.decision_id,
            "timestamp": r.timestamp.isoformat(),
            "started_at": r.timestamp.isoformat(),
            "action": r.action,
            "mode": r.action,
            "status": "completed" if r.status in ("SUCCESS", "SIMULATED", "COMPLETED") else r.status.lower(),
            "duration_ms": r.duration_ms or 0,
            "volume_ml": r.volume_ml or 0.0,
            "disease": r.disease,
            "plants_affected": r.plants_affected,
            "plants_targeted": r.plants_targeted,
            "severity": r.severity,
            "reason": r.reason or r.message,
            "ack_state": r.ack_state,
            "ai_context": r.ai_context_json or {},
            "message": r.message,
            "error_message": r.message if r.status in ("FAILED", "ERROR", "REJECTED", "BLOCKED") else None,
        }
        for r in records
    ]

# ==========================================
# 4. Farmer Notifications & Alerts Endpoints
# ==========================================

@router.get("/notifications")
async def flutter_get_notifications(
    field_id: Optional[str] = None,
    device_id: Optional[str] = None,
    unread_only: bool = False,
    limit: int = 50,
    db: AsyncSession = Depends(get_sqlite_db),
):
    notifs = await NotificationService.get_notifications(
        db=db,
        field_id=field_id,
        device_id=device_id,
        limit=limit,
        unread_only=unread_only,
    )
    return [
        {
            "id": n.id,
            "device_id": n.device_id,
            "field_id": n.field_id,
            "timestamp": n.timestamp.isoformat(),
            "type": n.type,
            "severity": n.severity,
            "title": n.title,
            "message": n.message,
            "source": n.source,
            "is_read": n.is_read,
            "decision_id": n.decision_id,
            "action_id": n.action_id,
            "stats": n.stats_json or {},
        }
        for n in notifs
    ]

@router.get("/notifications/active")
async def flutter_get_active_notifications(
    field_id: Optional[str] = None,
    device_id: Optional[str] = None,
    limit: int = 10,
    db: AsyncSession = Depends(get_sqlite_db),
):
    notifs = await NotificationService.get_notifications(
        db=db,
        field_id=field_id,
        device_id=device_id,
        limit=limit,
        unread_only=True,
    )
    return [
        {
            "id": n.id,
            "device_id": n.device_id,
            "field_id": n.field_id,
            "timestamp": n.timestamp.isoformat(),
            "type": n.type,
            "severity": n.severity,
            "title": n.title,
            "message": n.message,
            "source": n.source,
            "is_read": n.is_read,
            "decision_id": n.decision_id,
            "action_id": n.action_id,
            "stats": n.stats_json or {},
        }
        for n in notifs
    ]

@router.post("/notifications/{notification_id}/read")
async def flutter_mark_notification_read(
    notification_id: str,
    db: AsyncSession = Depends(get_sqlite_db),
):
    success = await NotificationService.mark_as_read(db=db, notification_id=notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.commit()
    return {"success": True, "id": notification_id}

# ==========================================
# 5. Real Field Statistics & Insights
# ==========================================

@router.get("/statistics")
async def flutter_get_statistics(
    field_id: str = "field-001",
    device_id: str = "device-001",
    db: AsyncSession = Depends(get_sqlite_db),
):
    """
    Computes real field statistics from database and live hardware telemetry.
    Zero fake or hardcoded values.
    """
    # 1. Total Action counts from ActionHistoryModel
    stmt_actions = select(ActionHistoryModel).where(ActionHistoryModel.field_id == field_id)
    res_actions = await db.execute(stmt_actions)
    all_actions = res_actions.scalars().all()

    total_actions = len(all_actions)
    total_sprays = sum(1 for a in all_actions if a.action == "SPRAY")
    total_irrigations = sum(1 for a in all_actions if a.action == "IRRIGATE")
    total_completed = sum(1 for a in all_actions if a.status in ("COMPLETED", "SUCCESS"))

    # 2. Latest Operation
    stmt_latest = (
        select(ActionHistoryModel)
        .where(ActionHistoryModel.field_id == field_id)
        .order_by(desc(ActionHistoryModel.timestamp))
        .limit(1)
    )
    res_latest = await db.execute(stmt_latest)
    latest_op = res_latest.scalar_one_or_none()

    latest_operation = None
    if latest_op:
        latest_operation = {
            "id": latest_op.id,
            "action": latest_op.action,
            "status": latest_op.status,
            "timestamp": latest_op.timestamp.isoformat(),
            "duration_seconds": (latest_op.duration_ms // 1000) if latest_op.duration_ms else 0,
            "plants_targeted": latest_op.plants_targeted,
            "disease": latest_op.disease,
            "reason": latest_op.reason or latest_op.message,
        }

    # 3. Field Health & AI Insights from DecisionModel
    stmt_decisions = (
        select(DecisionModel)
        .where(DecisionModel.field_id == field_id)
        .order_by(desc(DecisionModel.timestamp))
        .limit(10)
    )
    res_dec = await db.execute(stmt_decisions)
    recent_decisions = res_dec.scalars().all()

    latest_detection = None
    health_summary = "NO_DATA"
    if recent_decisions:
        latest_dec = recent_decisions[0]
        rec = latest_dec.primary_decision or "MONITOR"
        health_summary = "HEALTHY" if rec in ("MONITOR", "NO_SPRAY") else "ATTENTION_NEEDED"
        latest_detection = {
            "decision_id": latest_dec.id,
            "timestamp": latest_dec.timestamp.isoformat(),
            "primary_decision": latest_dec.primary_decision,
            "risk_level": latest_dec.risk_level,
        }

    # 4. Live Telemetry
    stat = esp32_service.get_status(device_id)
    is_connected = stat.get("esp32_connected", False)
    soil = stat.get("soil") if is_connected else None
    env = stat.get("environment") if is_connected else None

    return {
        "success": True,
        "field_id": field_id,
        "device_id": device_id,
        "field_health": {
            "summary": health_summary,
            "latest_detection": latest_detection,
            "recent_scans_count": len(recent_decisions),
        },
        "operations": {
            "total_actions": total_actions,
            "total_sprays": total_sprays,
            "total_irrigations": total_irrigations,
            "total_completed": total_completed,
            "latest_operation": latest_operation,
        },
        "telemetry": {
            "connected": is_connected,
            "soil_moisture_percent": soil.get("moisture_percent") if soil else None,
            "temperature_celsius": env.get("temperature_celsius") if env else None,
            "humidity_percent": env.get("humidity_percent") if env else None,
            "rain_detected": env.get("rain_detected") if env else None,
        },
    }

# ==========================================
# 4. WebSocket Live Telemetry Stream
# ==========================================

async def handle_telemetry_websocket(websocket: WebSocket, device_id: str):
    await websocket.accept()
    logger.info(f"WebSocket client connected for device '{device_id}'")
    try:
        while True:
            # Emit telemetry frame every 3 seconds using real esp32_service status
            stat = esp32_service.get_status(device_id)
            soil = stat.get("soil") or {}
            env = stat.get("environment") or {}
            is_connected = stat.get("esp32_connected", False)

            frame = {
                "type": "TELEMETRY",
                "device_id": device_id,
                "payload": {
                    "esp32_connected": is_connected,
                    "soil_moisture": soil.get("moisture_percent") if is_connected else None,
                    "air_temperature": env.get("temperature_celsius") if is_connected else None,
                    "humidity": env.get("humidity_percent") if is_connected else None,
                    "rain_detected": env.get("rain_detected") if is_connected else None,
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

@router.websocket("/ws/{device_id}")
async def websocket_device_stream(websocket: WebSocket, device_id: str):
    await handle_telemetry_websocket(websocket, device_id)

@ws_router.websocket("/ws/device/{device_id}")
@ws_router.websocket("/ws/{device_id}")
async def root_websocket_device_stream(websocket: WebSocket, device_id: str):
    await handle_telemetry_websocket(websocket, device_id)
