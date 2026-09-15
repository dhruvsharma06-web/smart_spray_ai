import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.database import Base, engine
from app.api import auth, farms, sensors, analysis, decision, devices, dashboard, assistant, alerts
import app.models
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger=logging.getLogger("smart-spray")
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield
app=FastAPI(title="Smart Farming Assistant Backend",version="1.0.0",description="Central integration backend for Smart Spray.",lifespan=lifespan)
@app.middleware("http")
async def request_logging(request:Request,call_next):
    logger.info("%s %s",request.method,request.url.path)
    try: response=await call_next(request); logger.info("%s %s -> %s",request.method,request.url.path,response.status_code); return response
    except Exception: logger.exception("Unhandled request error"); raise
@app.get("/health",tags=["system"])
def health(): return {"status":"ok"}
for r in [auth.router,farms.router,sensors.router,analysis.router,decision.router,devices.router,dashboard.router,assistant.router,alerts.router]: app.include_router(r)
