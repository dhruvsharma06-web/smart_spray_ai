from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.services.ownership import get_field_owned
from app.services.analysis import AnalysisOrchestrator
from app.services.audit import audit
router=APIRouter(prefix="/api",tags=["analysis"])

@router.post("/analysis")
async def analyze(field_id:int=Form(...), image:UploadFile=File(...), db:Session=Depends(get_db), user=Depends(get_current_user)):
    field=get_field_owned(db,user,field_id)
    if not image.content_type or not image.content_type.startswith("image/"): raise HTTPException(415,"Only image uploads are accepted")
    data=await image.read()
    from app.config import settings
    if len(data)>settings.max_image_bytes: raise HTTPException(413,"Image too large")
    try:
        a=AnalysisOrchestrator(); analysis,result,decision,decision_json,weather=await a.run(db,field,data,image.filename or "upload.jpg")
        audit(db,"AI_ANALYSIS_COMPLETED",user,"AIAnalysis",analysis.id); db.commit()
        return {"analysis_id":analysis.id,"analysis":result,"decision":decision_json,"weather":weather}
    except Exception as e:
        db.rollback(); audit(db,"AI_ANALYSIS_FAILED",user,metadata={"error":type(e).__name__}); db.commit(); raise HTTPException(502,"Analysis service unavailable or failed")
