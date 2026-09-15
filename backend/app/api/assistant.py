from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.auth.dependencies import get_current_user
from app.genai.client import GenAIService
class ExplainRequest(BaseModel):
    analysis: dict
    decision: dict
router=APIRouter(prefix="/api/assistant",tags=["assistant"])
@router.post("/explain")
async def explain(payload:ExplainRequest,user=Depends(get_current_user)): return await GenAIService().explain(payload.analysis,payload.decision)
