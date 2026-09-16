from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.services.ownership import get_device_owned
from app.iot.commands import validate_command, execute_local
from app.services.audit import audit
from app.models import SprayEvent
from datetime import datetime, timezone
import json
router=APIRouter(prefix="/api/devices",tags=["devices"])

@router.post("")
def create_device(field_id:int, device_uid:str, name:str, db:Session=Depends(get_db), user=Depends(get_current_user)):
    from app.models import Device
    from app.services.ownership import get_field_owned
    get_field_owned(db,user,field_id)
    d=Device(field_id=field_id,device_uid=device_uid,name=name)
    db.add(d); db.commit(); db.refresh(d); return {"id":d.id,"device_uid":d.device_uid,"status":d.status}

def command(device_id:int,action:str,db,user,decision_id:int|None=None, idempotency_key:str|None=None):
    from app.models import Decision
    d=get_device_owned(db,user,device_id)
    decision=None
    if action != "stop":
        if decision_id is None: raise HTTPException(422,"decision_id is required for actuator commands")
        decision_row=db.get(Decision,decision_id)
        if not decision_row or decision_row.field_id != d.field_id: raise HTTPException(404,"Decision not found")
        # Check decision expiry
        if decision_row.expires_at and decision_row.expires_at < datetime.now(timezone.utc):
            raise HTTPException(409, "Decision has expired")
        decision=decision_row.result
        if action == "irrigate" and decision_row.primary_decision not in {"IRRIGATE","SPRAY","WARN","MONITOR"}: raise HTTPException(409,"Decision does not authorize irrigation")
    validate_command(d,action,decision)
    
    # Idempotency check
    if idempotency_key:
        existing = db.query(SprayEvent).filter(SprayEvent.idempotency_key == idempotency_key).first()
        if existing:
            # Verify the existing event matches this request
            if existing.device_id == d.id and existing.action == action.upper() and existing.decision_id == decision_id:
                # Return existing event
                return {"event_id": existing.id, "device_id": d.id, "command": action.upper(), "status": existing.status, "idempotent": True}
            else:
                raise HTTPException(409, "Idempotency key already used for a different command")
    
    event=execute_local(db,d,action,decision_id)
    if idempotency_key:
        event.idempotency_key = idempotency_key
    audit(db,"DEVICE_COMMAND",user,"Device",d.id,{"action":action,"decision_id":decision_id,"idempotency_key":idempotency_key})
    db.commit(); db.refresh(event)
    return {"event_id":event.id,"device_id":d.id,"command":action.upper(),"status":event.status, "idempotent": False}
@router.post("/{device_id}/spray")
def spray(device_id:int,decision_id:int,idempotency_key:str|None=Header(None, alias="Idempotency-Key"),db:Session=Depends(get_db),user=Depends(get_current_user)):
    return command(device_id,"spray",db,user,decision_id,idempotency_key)
@router.post("/{device_id}/irrigate")
def irrigate(device_id:int,decision_id:int,idempotency_key:str|None=Header(None, alias="Idempotency-Key"),db:Session=Depends(get_db),user=Depends(get_current_user)): return command(device_id,"irrigate",db,user,decision_id,idempotency_key)
@router.post("/{device_id}/stop")
def stop(device_id:int,idempotency_key:str|None=Header(None, alias="Idempotency-Key"),db:Session=Depends(get_db),user=Depends(get_current_user)): return command(device_id,"stop",db,user,None,idempotency_key)
@router.get("/{device_id}/status")
def status(device_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    d=get_device_owned(db,user,device_id); return {"device_id":d.device_uid,"status":d.status,"last_seen_at":d.last_seen_at,"tank_level":d.tank_level,"pump_active":d.pump_active}
