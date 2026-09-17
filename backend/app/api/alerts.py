from fastapi import APIRouter, Depends
from sqlalchemy import select
from app.database import get_db
from app.models import Alert
from app.auth.dependencies import get_current_user
from app.services.ownership import get_field_owned
router=APIRouter(prefix="/api/alerts",tags=["alerts"])
@router.get("")
def list_alerts(field_id:int|None=None,db=Depends(get_db),user=Depends(get_current_user)):
    q=select(Alert).join(__import__('app.models',fromlist=['Field']).Field).join(__import__('app.models',fromlist=['Farm']).Farm).where(__import__('app.models',fromlist=['Farm']).Farm.owner_id==user.id)
    if field_id is not None: get_field_owned(db,user,field_id); q=q.where(Alert.field_id==field_id)
    return list(db.scalars(q.order_by(Alert.created_at.desc()).limit(200)))
