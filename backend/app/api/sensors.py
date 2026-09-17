from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Device, SensorReading, Field, Farm
from app.schemas.common import TelemetryIn, TelemetryOut
from app.auth.dependencies import get_current_user
router=APIRouter(prefix="/api/sensors",tags=["sensors"])

@router.post("/telemetry", response_model=TelemetryOut, status_code=201)
def telemetry(p: TelemetryIn, db=Depends(get_db)):
    d=db.scalar(select(Device).where(Device.device_uid==p.device_id))
    if not d: raise HTTPException(404,"Device not found")
    d.status="ONLINE"; d.last_seen_at=datetime.now(timezone.utc); d.tank_level=p.tank_level; d.pump_active=p.pump
    r=SensorReading(device_id=d.id,device_timestamp=p.timestamp,server_timestamp=datetime.now(timezone.utc),payload=p.model_dump(mode="json")); db.add(r); db.commit(); db.refresh(r)
    return TelemetryOut(reading_id=r.id,device_id=p.device_id,device_timestamp=r.device_timestamp,server_timestamp=r.server_timestamp)

@router.get("/latest")
def latest(device_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    d=db.scalar(select(Device).join(Field).join(Farm).where(Device.device_uid==device_id,Farm.owner_id==user.id))
    if not d: raise HTTPException(404,"Device not found")
    r=db.scalar(select(SensorReading).where(SensorReading.device_id==d.id).order_by(SensorReading.device_timestamp.desc()))
    return {"device_id":device_id,"reading":r.payload if r else None,"device_timestamp":r.device_timestamp if r else None,"server_timestamp":r.server_timestamp if r else None}

@router.get("/history")
def history(device_id: str, limit:int=100, db=Depends(get_db), user=Depends(get_current_user)):
    d=db.scalar(select(Device).join(Field).join(Farm).where(Device.device_uid==device_id,Farm.owner_id==user.id))
    if not d: raise HTTPException(404,"Device not found")
    limit=min(max(limit,1),1000); rows=list(db.scalars(select(SensorReading).where(SensorReading.device_id==d.id).order_by(SensorReading.device_timestamp.desc()).limit(limit)))
    return [{"id":r.id,"device_timestamp":r.device_timestamp,"server_timestamp":r.server_timestamp,"payload":r.payload} for r in rows]
