import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.db.sqlite import (
    ActionHistoryModel,
    AnalysisModel,
    DecisionModel,
    DeviceModel,
    FieldModel,
    TelemetryModel,
    ZoneModel,
    gen_id,
    get_sqlite_db,
    utc_now,
)
from app.demo.scenarios import get_demo_scenario
from app.iot.mock_service import mock_iot_service
from app.services.actuator_authorization import ActuatorAuthorizationService

logger = logging.getLogger("canonical-api")
router = APIRouter(tags=["canonical"])

# ==========================================
# Pydantic Request & Response Schemas
# ==========================================

class FieldCreate(BaseModel):
    id: Optional[str] = None
    name: str
    crop_type: str = "Tomato"
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class DeviceCreate(BaseModel):
    id: str
    field_id: str
    name: str

class TelemetryCreate(BaseModel):
    field_id: str
    device_id: str
    soil_moisture: Optional[float] = None
    soil_temperature: Optional[float] = None
    air_temperature: Optional[float] = None
    humidity: Optional[float] = None
    rainfall: Optional[float] = None
    timestamp: Optional[str] = None

class DeviceCommandRequest(BaseModel):
    action: str  # SPRAY, IRRIGATE, STOP, EMERGENCY_STOP, RESET_EMERGENCY_STOP
    decision_id: Optional[str] = None
    duration_ms: Optional[int] = 5000
    volume_ml: Optional[float] = 250.0
    reason: Optional[str] = None

# ==========================================
# Helper: Lazy Auto-Seed Default Field & Device
# ==========================================

async def ensure_default_field_and_device(db: AsyncSession, field_id: str = "field-001", device_id: str = "device-001"):
    # Field
    res = await db.execute(select(FieldModel).where(FieldModel.id == field_id))
    f = res.scalar_one_or_none()
    if not f:
        f = FieldModel(
            id=field_id,
            name="Demo Tomato Field",
            crop_type="Tomato",
            latitude=19.0760,
            longitude=72.8777,
        )
        db.add(f)
        await db.flush()

    # Device
    res_dev = await db.execute(select(DeviceModel).where(DeviceModel.id == device_id))
    d = res_dev.scalar_one_or_none()
    if not d:
        d = DeviceModel(
            id=device_id,
            field_id=field_id,
            name="SmartSpray Controller",
            status="ONLINE",
            battery=95,
            tank_level=88,
            current_action="IDLE",
        )
        db.add(d)
        await db.flush()
    await db.commit()

# ==========================================
# 1. Field Management Endpoints
# ==========================================

@router.post("/fields", status_code=status.HTTP_201_CREATED)
async def create_field(payload: FieldCreate, db: AsyncSession = Depends(get_sqlite_db)):
    field_id = payload.id or gen_id("field-")
    res = await db.execute(select(FieldModel).where(FieldModel.id == field_id))
    existing = res.scalar_one_or_none()
    if existing:
        existing.name = payload.name
        existing.crop_type = payload.crop_type
        existing.latitude = payload.latitude
        existing.longitude = payload.longitude
        await db.commit()
        return {
            "id": existing.id,
            "name": existing.name,
            "crop_type": existing.crop_type,
            "latitude": existing.latitude,
            "longitude": existing.longitude,
            "created_at": existing.created_at.isoformat(),
        }

    field = FieldModel(
        id=field_id,
        name=payload.name,
        crop_type=payload.crop_type,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    db.add(field)
    await db.commit()
    await db.refresh(field)
    logger.info(f"Created field '{field.id}' ({field.name})")
    return {
        "id": field.id,
        "name": field.name,
        "crop_type": field.crop_type,
        "latitude": field.latitude,
        "longitude": field.longitude,
        "created_at": field.created_at.isoformat(),
    }

@router.get("/fields/{field_id}/latest")
async def get_field_latest(field_id: str, db: AsyncSession = Depends(get_sqlite_db)):
    f_res = await db.execute(select(FieldModel).where(FieldModel.id == field_id))
    field = f_res.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail=f"Field '{field_id}' not found")

    # Latest telemetry
    t_stmt = select(TelemetryModel).where(TelemetryModel.field_id == field_id).order_by(desc(TelemetryModel.timestamp)).limit(1)
    t_res = await db.execute(t_stmt)
    latest_tel = t_res.scalar_one_or_none()

    # Latest analysis
    a_stmt = select(AnalysisModel).where(AnalysisModel.field_id == field_id).order_by(desc(AnalysisModel.timestamp)).limit(1)
    a_res = await db.execute(a_stmt)
    latest_ana = a_res.scalar_one_or_none()

    # Latest decision
    d_stmt = select(DecisionModel).where(DecisionModel.field_id == field_id).order_by(desc(DecisionModel.timestamp)).limit(1)
    d_res = await db.execute(d_stmt)
    latest_dec = d_res.scalar_one_or_none()

    # Devices
    dev_stmt = select(DeviceModel).where(DeviceModel.field_id == field_id)
    dev_res = await db.execute(dev_stmt)
    devices = dev_res.scalars().all()

    return {
        "field": {
            "id": field.id,
            "name": field.name,
            "crop_type": field.crop_type,
            "latitude": field.latitude,
            "longitude": field.longitude,
        },
        "devices": [
            {
                "id": d.id,
                "name": d.name,
                "status": d.status,
                "battery": d.battery,
                "tank_level": d.tank_level,
                "current_action": d.current_action,
                "last_seen": d.last_seen.isoformat(),
            }
            for d in devices
        ],
        "latest_telemetry": {
            "id": latest_tel.id,
            "soil_moisture": latest_tel.soil_moisture,
            "soil_temperature": latest_tel.soil_temperature,
            "air_temperature": latest_tel.air_temperature,
            "humidity": latest_tel.humidity,
            "rainfall": latest_tel.rainfall,
            "timestamp": latest_tel.timestamp.isoformat(),
        } if latest_tel else None,
        "latest_analysis": {
            "id": latest_ana.id,
            "timestamp": latest_ana.timestamp.isoformat(),
            "raw_ai_result": latest_ana.raw_ai_result_json,
        } if latest_ana else None,
        "latest_decision": {
            "id": latest_dec.id,
            "primary_decision": latest_dec.primary_decision,
            "risk_level": latest_dec.risk_level,
            "actions": latest_dec.actions_json,
            "warnings": latest_dec.warnings_json,
            "requires_confirmation": latest_dec.requires_confirmation,
            "timestamp": latest_dec.timestamp.isoformat(),
        } if latest_dec else None,
    }

@router.get("/fields/{field_id}/history")
async def get_field_history(field_id: str, limit: int = 50, db: AsyncSession = Depends(get_sqlite_db)):
    a_stmt = select(AnalysisModel).where(AnalysisModel.field_id == field_id).order_by(desc(AnalysisModel.timestamp)).limit(limit)
    a_res = await db.execute(a_stmt)
    analyses = a_res.scalars().all()

    d_stmt = select(DecisionModel).where(DecisionModel.field_id == field_id).order_by(desc(DecisionModel.timestamp)).limit(limit)
    d_res = await db.execute(d_stmt)
    decisions = d_res.scalars().all()

    act_stmt = select(ActionHistoryModel).where(ActionHistoryModel.field_id == field_id).order_by(desc(ActionHistoryModel.timestamp)).limit(limit)
    act_res = await db.execute(act_stmt)
    actions = act_res.scalars().all()

    return {
        "field_id": field_id,
        "analyses": [
            {"id": a.id, "timestamp": a.timestamp.isoformat(), "raw_ai_result": a.raw_ai_result_json}
            for a in analyses
        ],
        "decisions": [
            {
                "id": d.id,
                "analysis_id": d.analysis_id,
                "primary_decision": d.primary_decision,
                "risk_level": d.risk_level,
                "actions": d.actions_json,
                "warnings": d.warnings_json,
                "requires_confirmation": d.requires_confirmation,
                "timestamp": d.timestamp.isoformat(),
            }
            for d in decisions
        ],
        "actions": [
            {
                "id": act.id,
                "device_id": act.device_id,
                "decision_id": act.decision_id,
                "action": act.action,
                "status": act.status,
                "duration_ms": act.duration_ms,
                "volume_ml": act.volume_ml,
                "message": act.message,
                "timestamp": act.timestamp.isoformat(),
            }
            for act in actions
        ],
    }

@router.get("/fields/{field_id}/zones")
async def get_field_zones(field_id: str, db: AsyncSession = Depends(get_sqlite_db)):
    z_stmt = select(ZoneModel).where(ZoneModel.field_id == field_id)
    z_res = await db.execute(z_stmt)
    zones = z_res.scalars().all()
    if not zones:
        # Provide default polygon for demo if none configured
        return [
            {
                "id": f"zone-{field_id}-1",
                "field_id": field_id,
                "name": "North Sector (Tomatoes)",
                "boundary": [
                    {"latitude": 19.0760, "longitude": 72.8770},
                    {"latitude": 19.0765, "longitude": 72.8770},
                    {"latitude": 19.0765, "longitude": 72.8778},
                    {"latitude": 19.0760, "longitude": 72.8778},
                ],
            }
        ]
    return [
        {"id": z.id, "field_id": z.field_id, "name": z.name, "boundary": z.boundary_json}
        for z in zones
    ]

# ==========================================
# 2. Device Management Endpoints
# ==========================================

@router.post("/devices", status_code=status.HTTP_201_CREATED)
async def create_device(payload: DeviceCreate, db: AsyncSession = Depends(get_sqlite_db)):
    # Check field exists
    f_res = await db.execute(select(FieldModel).where(FieldModel.id == payload.field_id))
    if not f_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Field '{payload.field_id}' does not exist")

    dev_res = await db.execute(select(DeviceModel).where(DeviceModel.id == payload.id))
    existing = dev_res.scalar_one_or_none()
    if existing:
        existing.name = payload.name
        existing.field_id = payload.field_id
        await db.commit()
        return {"id": existing.id, "name": existing.name, "field_id": existing.field_id, "status": existing.status}

    device = DeviceModel(
        id=payload.id,
        field_id=payload.field_id,
        name=payload.name,
        status="ONLINE",
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)
    logger.info(f"Registered device '{device.id}' to field '{device.field_id}'")
    return {
        "id": device.id,
        "name": device.name,
        "field_id": device.field_id,
        "status": device.status,
    }

@router.get("/devices/{device_id}/status")
async def get_device_status(device_id: str, db: AsyncSession = Depends(get_sqlite_db)):
    dev_res = await db.execute(select(DeviceModel).where(DeviceModel.id == device_id))
    device = dev_res.scalar_one_or_none()
    if not device:
        # Fallback to in-memory mock IoT status or 404
        mock_stat = mock_iot_service.get_status(device_id)
        return mock_stat

    mock_stat = mock_iot_service.get_status(device_id)
    return {
        "device_id": device.id,
        "name": device.name,
        "field_id": device.field_id,
        "status": mock_stat["status"],
        "battery": mock_stat["battery"],
        "tank_level": mock_stat["tank_level"],
        "current_action": mock_stat["current_action"],
        "last_seen": mock_stat["last_seen"],
    }

@router.post("/devices/{device_id}/command")
async def post_device_command(
    device_id: str,
    payload: DeviceCommandRequest,
    db: AsyncSession = Depends(get_sqlite_db),
):
    action = payload.action.strip().upper()
    logger.info(f"Received command '{action}' for device '{device_id}'")

    # 1. Independent Fail-Safe Cutoffs: STOP & EMERGENCY_STOP bypass Decision authorization
    if action == "STOP":
        iot_res = mock_iot_service.stop(device_id)
        # Log to DB action history
        dev_res = await db.execute(select(DeviceModel).where(DeviceModel.id == device_id))
        dev = dev_res.scalar_one_or_none()
        field_id = dev.field_id if dev else "field-001"
        act_entry = ActionHistoryModel(
            id=gen_id("act-"),
            field_id=field_id,
            device_id=device_id,
            decision_id=None,
            action="STOP",
            status=iot_res["status"],
            message=iot_res["message"],
        )
        db.add(act_entry)
        await db.commit()
        return iot_res

    if action == "EMERGENCY_STOP":
        reason = payload.reason or "Manual emergency cutoff engaged"
        iot_res = mock_iot_service.emergency_stop(device_id, reason=reason)
        dev_res = await db.execute(select(DeviceModel).where(DeviceModel.id == device_id))
        dev = dev_res.scalar_one_or_none()
        field_id = dev.field_id if dev else "field-001"
        act_entry = ActionHistoryModel(
            id=gen_id("act-"),
            field_id=field_id,
            device_id=device_id,
            decision_id=None,
            action="EMERGENCY_STOP",
            status=iot_res["status"],
            message=f"EMERGENCY CUTOFF: {reason}",
        )
        db.add(act_entry)
        await db.commit()
        return iot_res

    if action == "RESET_EMERGENCY_STOP":
        iot_res = mock_iot_service.reset_emergency_stop(device_id)
        return iot_res

    # 2. Operational Actuations (SPRAY, IRRIGATE) MUST pass single authoritative safety gate
    auth_result = await ActuatorAuthorizationService.authorize_action(
        db=db,
        device_id=device_id,
        action=action,
        decision_id=payload.decision_id,
    )

    if not auth_result.authorized:
        logger.warning(f"Actuator command '{action}' REJECTED: {auth_result.reason}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "authorized": False,
                "action": action,
                "device_id": device_id,
                "reason": auth_result.reason,
            },
        )

    # 3. Dispatched to IoT Service
    if action == "SPRAY":
        iot_res = mock_iot_service.spray(
            device_id=device_id,
            duration_ms=payload.duration_ms or 5000,
            volume_ml=payload.volume_ml or 250.0,
        )
    elif action == "IRRIGATE":
        iot_res = mock_iot_service.irrigate(
            device_id=device_id,
            duration_ms=payload.duration_ms or 10000,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported action '{action}'")

    # 4. Record action history
    act_entry = ActionHistoryModel(
        id=gen_id("act-"),
        field_id=auth_result.field_id or "field-001",
        device_id=device_id,
        decision_id=auth_result.decision_id,
        action=action,
        status=iot_res["status"],
        duration_ms=iot_res.get("duration_ms"),
        volume_ml=iot_res.get("volume_ml"),
        message=iot_res.get("message"),
    )
    db.add(act_entry)
    await db.commit()

    return {
        "authorized": True,
        "executed": True,
        "command_id": act_entry.id,
        "decision_id": auth_result.decision_id,
        "iot_result": iot_res,
    }

# ==========================================
# 3. Telemetry Ingestion Endpoint
# ==========================================

@router.post("/telemetry", status_code=status.HTTP_201_CREATED)
async def post_telemetry(payload: TelemetryCreate, db: AsyncSession = Depends(get_sqlite_db)):
    t_id = gen_id("tel-")
    tel = TelemetryModel(
        id=t_id,
        field_id=payload.field_id,
        device_id=payload.device_id,
        soil_moisture=payload.soil_moisture,
        soil_temperature=payload.soil_temperature,
        air_temperature=payload.air_temperature,
        humidity=payload.humidity,
        rainfall=payload.rainfall,
    )
    db.add(tel)

    # Update device last_seen
    d_res = await db.execute(select(DeviceModel).where(DeviceModel.id == payload.device_id))
    device = d_res.scalar_one_or_none()
    if device:
        device.last_seen = utc_now()

    await db.commit()
    logger.info(f"Ingested telemetry '{t_id}' for field '{payload.field_id}' device '{payload.device_id}'")
    return {
        "status": "INGESTED",
        "id": tel.id,
        "field_id": tel.field_id,
        "device_id": tel.device_id,
        "timestamp": tel.timestamp.isoformat(),
    }

# ==========================================
# 4. Central Pipeline: POST /analyze
# ==========================================

@router.post("/analyze")
async def analyze_field(
    image: UploadFile = File(...),
    field_id: str = Form("field-001"),
    sensor_data: Optional[str] = Form(None),
    weather_data: Optional[str] = Form(None),
    crop_stage: str = Form("vegetative"),
    explainer_mode: str = Form("auto"),
    demo_scenario: Optional[str] = Query(None),
    x_demo_scenario: Optional[str] = Header(None, alias="X-Demo-Scenario"),
    db: AsyncSession = Depends(get_sqlite_db),
):
    """
    Central End-to-End Orchestrator:
    1. Parse inputs & validate field
    2. Persist telemetry if provided
    3. Run Person 1 AI Service (:8001) OR deterministic DEMO scenario
    4. Store AI analysis
    5. Run Person 3 Decision Engine (:8002)
    6. Store DecisionResult with TTL & UUID
    7. Single Safety Gate: ActuatorAuthorizationService
    8. Dispatched to Mock IoT adapter if authorized
    9. Record Action History & return unified JSON response
    """
    # 1. Parse JSON Form strings safely
    parsed_sensor: Dict[str, Any] = {}
    if sensor_data:
        try:
            parsed_sensor = json.loads(sensor_data)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Malformed sensor_data JSON")

    parsed_weather: Dict[str, Any] = {}
    if weather_data:
        try:
            parsed_weather = json.loads(weather_data)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Malformed weather_data JSON")

    # Ensure field and device exist
    await ensure_default_field_and_device(db, field_id=field_id, device_id="device-001")

    # Read image content
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")

    # 2. Persist telemetry snapshot if provided
    if parsed_sensor or parsed_weather:
        soil_info = parsed_sensor.get("soil", {})
        air_info = parsed_sensor.get("air", {})
        tel_record = TelemetryModel(
            id=gen_id("tel-"),
            field_id=field_id,
            device_id="device-001",
            soil_moisture=soil_info.get("moisture_percent") or soil_info.get("moisture"),
            soil_temperature=soil_info.get("temperature_celsius") or soil_info.get("temperature"),
            air_temperature=air_info.get("temperature_celsius") or parsed_weather.get("temperature"),
            humidity=air_info.get("humidity_percent") or parsed_weather.get("humidity"),
            rainfall=air_info.get("rainfall_mm") or parsed_weather.get("rainfall"),
        )
        db.add(tel_record)
        await db.flush()

    # 3. Determine Execution Mode: DEMO vs REAL
    active_scenario_name = x_demo_scenario or demo_scenario
    is_demo = bool(settings.demo_mode or active_scenario_name)
    demo_scenario_data = None

    if is_demo:
        scenario_key = active_scenario_name or settings.demo_default_scenario or "TOMATO_EARLY_BLIGHT"
        demo_scenario_data = get_demo_scenario(scenario_key)
        if not demo_scenario_data:
            logger.warning(f"Demo scenario '{scenario_key}' not found; falling back to TOMATO_EARLY_BLIGHT")
            demo_scenario_data = get_demo_scenario("TOMATO_EARLY_BLIGHT")

    ai_output: Dict[str, Any] = {}
    is_real_ai = False

    if demo_scenario_data:
        # Deterministic Demo AI Result
        ai_output = demo_scenario_data["analysis"]
        if not parsed_sensor:
            parsed_sensor = demo_scenario_data["sensor_data"]
        if not parsed_weather:
            parsed_weather = demo_scenario_data["weather_data"]
        logger.info(f"[ANALYSIS] Running in DEMO MODE with scenario: {demo_scenario_data['description']}")
    else:
        # Call Real Person 1 AI Service (:8001)
        from app.ai.client import AIService
        ai_client = AIService(base_url=settings.ai_service_url)
        try:
            ai_output = await ai_client.analyze(
                image_bytes=image_bytes,
                filename=image.filename or "field.jpg",
                sensor_data=parsed_sensor,
                weather_data=parsed_weather,
                crop_stage=crop_stage,
            )
            is_real_ai = True
        except Exception as e:
            logger.error(f"Failed to communicate with Person 1 AI Service (:8001): {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Person 1 AI Service (:8001) unavailable: {str(e)}",
            )
        finally:
            await ai_client.close()

    # 4. Persist AI Analysis Record
    analysis_id = gen_id("ana-")
    analysis_entry = AnalysisModel(
        id=analysis_id,
        field_id=field_id,
        raw_ai_result_json=ai_output,
        image_metadata={"filename": image.filename, "bytes": len(image_bytes), "mode": "DEMO" if not is_real_ai else "PRODUCTION"},
    )
    db.add(analysis_entry)
    await db.flush()

    # 5. Call Person 3 Decision Engine
    # When in demo mode without live decision service, use imported DecisionEngine directly
    # Otherwise use DecisionService client (:8002)
    decision_output: Dict[str, Any] = {}
    is_real_de = False

    try:
        from app.decision.client import DecisionService
        de_client = DecisionService(base_url=settings.decision_service_url)
        decision_req_payload = {
            "analysis": ai_output,
            "sensor_data": parsed_sensor,
            "weather_data": parsed_weather,
            "field_id": 1,
        }
        decision_output = await de_client.decide(decision_req_payload)
        is_real_de = True
        await de_client.close()
    except Exception as e:
        logger.warning(f"Person 3 HTTP service unavailable ({e}); evaluating via DecisionEngine directly")
        try:
            from decision.engine import decision_engine
            from decision.models import DecisionRequest
            req = DecisionRequest(
                analysis=ai_output,
                sensor_data=parsed_sensor,
                weather_data=parsed_weather,
                field_id=1,
            )
            eval_res = decision_engine.evaluate(req)
            decision_output = eval_res.model_dump(mode="json")
        except Exception as de_err:
            logger.error(f"Decision Engine evaluation failed: {de_err}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Person 3 Decision Engine unavailable: {str(de_err)}",
            )

    # 6. Persist Decision Record
    decision_id = gen_id("dec-")
    ttl_seconds = settings.decision_ttl_seconds
    expires_at = utc_now() + timedelta(seconds=ttl_seconds)

    decision_entry = DecisionModel(
        id=decision_id,
        analysis_id=analysis_id,
        field_id=field_id,
        primary_decision=decision_output.get("primary_decision", "MONITOR"),
        risk_level=decision_output.get("risk_level", "LOW"),
        actions_json=decision_output.get("actions", []),
        warnings_json=decision_output.get("warnings", []),
        requires_confirmation=bool(decision_output.get("requires_confirmation", False)),
        raw_decision_json=decision_output,
        expires_at=expires_at,
    )
    db.add(decision_entry)
    await db.flush()

    # 7. Actuator Safety Gate: ActuatorAuthorizationService
    target_device_id = "device-001"
    primary_decision = str(decision_output.get("primary_decision", "")).upper()

    actuation_info: Dict[str, Any] = {
        "authorized": False,
        "executed": False,
        "action": primary_decision,
        "status": "INHIBITED",
        "reason": "Action does not require operational actuation",
        "device_id": target_device_id,
        "is_real_hardware": False,
    }

    if primary_decision in ("SPRAY", "IRRIGATE"):
        auth_res = await ActuatorAuthorizationService.authorize_action(
            db=db,
            device_id=target_device_id,
            action=primary_decision,
            decision_id=decision_id,
        )

        if auth_res.authorized:
            if primary_decision == "SPRAY":
                iot_res = mock_iot_service.spray(device_id=target_device_id)
            else:
                iot_res = mock_iot_service.irrigate(device_id=target_device_id)

            actuation_info.update({
                "authorized": True,
                "executed": True,
                "status": iot_res["status"],
                "reason": iot_res["message"],
                "duration_ms": iot_res.get("duration_ms"),
                "volume_ml": iot_res.get("volume_ml"),
            })

            # Record action history
            act_entry = ActionHistoryModel(
                id=gen_id("act-"),
                field_id=field_id,
                device_id=target_device_id,
                decision_id=decision_id,
                action=primary_decision,
                status=iot_res["status"],
                duration_ms=iot_res.get("duration_ms"),
                volume_ml=iot_res.get("volume_ml"),
                message=iot_res["message"],
            )
            db.add(act_entry)
        else:
            actuation_info.update({
                "authorized": False,
                "executed": False,
                "status": "BLOCKED",
                "reason": auth_res.reason,
            })
    elif primary_decision == "DELAY_SPRAY":
        actuation_info.update({
            "status": "DELAYED",
            "reason": "Spray delayed by Decision Engine (weather or high rain probability)",
        })
    elif primary_decision == "WARN":
        actuation_info.update({
            "status": "WARNING",
            "reason": "Advisory warning issued; operational action not authorized",
        })

    await db.commit()

    return {
        "analysis_id": analysis_id,
        "analysis": ai_output,
        "decision_id": decision_id,
        "decision": decision_output,
        "actuation": actuation_info,
        "execution_metadata": {
            "ai_source": "REAL_AI_SERVICE" if is_real_ai else "DEMO_AI_RESULT",
            "decision_source": "REAL_DECISION_SERVICE" if is_real_de else "LOCAL_DECISION_ENGINE",
            "actuation_type": "SIMULATED_MOCK_IOT",
            "demo_scenario": demo_scenario_data["description"] if demo_scenario_data else None,
        },
    }
