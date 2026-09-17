from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import Farm, Field, Device, Alert, AIAnalysis, Decision, SensorReading
from app.services.ownership import get_field_owned
router=APIRouter(prefix="/api",tags=["dashboard"])
@router.get("/dashboard")
def dashboard(db=Depends(get_db),user=Depends(get_current_user)):
    farms=list(db.scalars(select(Farm).where(Farm.owner_id==user.id))); fields=list(db.scalars(select(Field).join(Farm).where(Farm.owner_id==user.id)))
    return {"farms":len(farms),"fields":len(fields),"devices":db.scalar(select(func.count(Device.id)).join(Field).join(Farm).where(Farm.owner_id==user.id)) or 0,"active_alerts":db.scalar(select(func.count(Alert.id)).join(Field).join(Farm).where(Farm.owner_id==user.id,Alert.acknowledged==False)) or 0}
@router.get("/fields/{field_id}/health")
def health(field_id:int,db=Depends(get_db),user=Depends(get_current_user)):
    f=get_field_owned(db,user,field_id); a=db.scalar(select(AIAnalysis).where(AIAnalysis.field_id==field_id).order_by(AIAnalysis.created_at.desc())); return {"field_id":f.id,"crop":f.crop,"latest_analysis":a.raw_result if a else None}
@router.get("/fields/{field_id}/risk")
def risk(field_id:int,db=Depends(get_db),user=Depends(get_current_user)):
    get_field_owned(db,user,field_id); a=db.scalar(select(AIAnalysis).where(AIAnalysis.field_id==field_id).order_by(AIAnalysis.created_at.desc())); return {"field_id":field_id,"climate_risk":(a.raw_result.get("climate_risk") if a else None)}
@router.get("/fields/{field_id}/history")
def history(field_id:int,limit:int=50,db=Depends(get_db),user=Depends(get_current_user)):
    get_field_owned(db,user,field_id); limit=min(max(limit,1),200); analyses=list(db.scalars(select(AIAnalysis).where(AIAnalysis.field_id==field_id).order_by(AIAnalysis.created_at.desc()).limit(limit))); decisions=list(db.scalars(select(Decision).where(Decision.field_id==field_id).order_by(Decision.created_at.desc()).limit(limit))); alerts=list(db.scalars(select(Alert).where(Alert.field_id==field_id).order_by(Alert.created_at.desc()).limit(limit))); return {"analyses":[a.raw_result for a in analyses],"decisions":[d.result for d in decisions],"alerts":[a.message for a in alerts]}
