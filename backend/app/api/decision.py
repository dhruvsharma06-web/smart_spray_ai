from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.services.ownership import get_field_owned
from app.decision.client import DecisionService
from app.models import Decision
router=APIRouter(prefix="/api/decision",tags=["decision"])
@router.post("")
async def decide(field_id:int,payload:dict,db:Session=Depends(get_db),user=Depends(get_current_user)):
    get_field_owned(db,user,field_id); result=await DecisionService().decide(payload); d=Decision(field_id=field_id,primary_decision=result["primary_decision"],risk_level=result.get("risk_level","UNKNOWN"),result=result); db.add(d); db.commit(); db.refresh(d); return {"decision_id":d.id,**result}
