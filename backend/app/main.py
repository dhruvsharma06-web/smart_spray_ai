import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.database import Base, engine
from app.db.sqlite import init_sqlite_db
from app.api import auth, farms, sensors, analysis, decision, devices, dashboard, assistant, alerts
from app.api import canonical, flutter_compat
import app.models

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("smart-spray")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize both legacy sync and new async SQLite prototype tables
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.warning(f"Sync DB create_all skipped: {e}")
    await init_sqlite_db()
    logger.info("SQLite prototype database tables initialized.")
    yield

app = FastAPI(
    title="Smart Farming Assistant Backend",
    version="1.0.0",
    description="Central integration backend for Smart Spray with SQLite prototype layer.",
    lifespan=lifespan,
)

# CORS Configuration for Flutter Prototype
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def request_logging(request: Request, call_next):
    logger.info("%s %s", request.method, request.url.path)
    try:
        response = await call_next(request)
        logger.info("%s %s -> %s", request.method, request.url.path, response.status_code)
        return response
    except Exception:
        logger.exception("Unhandled request error")
        raise

@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "app": settings.app_name, "database": "sqlite_prototype"}

# Include Canonical Prototype and Flutter Compatibility Routers
app.include_router(canonical.router)
app.include_router(flutter_compat.router)
app.include_router(flutter_compat.ws_router)

# Include Enterprise Routers
for r in [auth.router, farms.router, sensors.router, analysis.router, decision.router, devices.router, dashboard.router, assistant.router, alerts.router]:
    app.include_router(r)

