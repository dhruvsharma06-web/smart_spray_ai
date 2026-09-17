from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Farm, Field
from app.schemas.common import FarmCreate, FarmOut, FieldCreate, FieldOut
from app.auth.dependencies import get_current_user
from app.services.ownership import get_farm_owned, get_field_owned
router=APIRouter(prefix="/api", tags=["farms & fields"])

@router.post("/farms", response_model=FarmOut, status_code=201)
def create_farm(p: FarmCreate, db: Session=Depends(get_db), user=Depends(get_current_user)):
    f=Farm(owner_id=user.id,name=p.name,location=p.location); db.add(f); db.commit(); db.refresh(f); return f
@router.get("/farms", response_model=list[FarmOut])
def list_farms(db=Depends(get_db), user=Depends(get_current_user)):
    return list(db.scalars(select(Farm).where(Farm.owner_id==user.id)))
@router.post("/fields", response_model=FieldOut, status_code=201)
def create_field(p: FieldCreate, db=Depends(get_db), user=Depends(get_current_user)):
    get_farm_owned(db,user,p.farm_id); x=Field(**p.model_dump()); db.add(x); db.commit(); db.refresh(x); return x
@router.get("/fields", response_model=list[FieldOut])
def list_fields(db=Depends(get_db), user=Depends(get_current_user)):
    return list(db.scalars(select(Field).join(Farm).where(Farm.owner_id==user.id)))
