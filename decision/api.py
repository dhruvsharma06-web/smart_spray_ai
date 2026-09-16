import logging
from fastapi import FastAPI, HTTPException, status
try:
    from .models import DecisionRequest, DecisionResponse
    from .engine import decision_engine
except ImportError:
    from models import DecisionRequest, DecisionResponse
    from engine import decision_engine

logger = logging.getLogger("decision-engine")

app = FastAPI(
    title="Smart Spray Decision Engine",
    version="1.0.0",
    description="Deterministic agronomic rule engine for precision agriculture",
)


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    return {
        "status": "ok",
        "service": "decision-engine",
    }


@app.post("/decision", response_model=DecisionResponse, status_code=status.HTTP_200_OK)
def evaluate_decision(request: DecisionRequest):
    try:
        decision = decision_engine.evaluate(request)
        return decision
    except Exception as e:
        logger.error(f"Error evaluating decision: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Decision Engine evaluation failure: {str(e)}",
        )
