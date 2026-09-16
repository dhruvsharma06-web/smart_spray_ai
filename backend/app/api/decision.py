from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime, timedelta, timezone
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.services.ownership import get_field_owned
from app.decision.client import DecisionService
from app.models import Decision
from pydantic import ValidationError
from app.config import settings
router=APIRouter(prefix="/api/decision",tags=["decision"])
@router.post("")
async def decide(field_id:int,payload:dict,db:Session=Depends(get_db),user=Depends(get_current_user)):
    get_field_owned(db,user,field_id)
    decision_service = DecisionService()
    try:
        result = await decision_service.decide(payload)
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(seconds=settings.decision_ttl_seconds)
        d = Decision(field_id=field_id, primary_decision=result["primary_decision"], risk_level=result.get("risk_level","UNKNOWN"), result=result, created_at=created_at, expires_at=expires_at)
        db.add(d); db.commit(); db.refresh(d)
        return {"decision_id": d.id, **result}
    except (ValidationError, ValueError) as e:
        raise HTTPException(502, f"Decision Engine response validation failed: {e}")
    finally:
        await decision_service.close()
