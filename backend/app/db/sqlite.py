import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from app.config import settings

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def gen_id(prefix: str = "") -> str:
    uid = str(uuid.uuid4())[:8]
    return f"{prefix}{uid}" if prefix else str(uuid.uuid4())

class SQLiteBase(DeclarativeBase):
    pass

class FieldModel(SQLiteBase):
    __tablename__ = "fields"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    crop_type: Mapped[str] = mapped_column(String(100), default="Tomato")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class ZoneModel(SQLiteBase):
    __tablename__ = "zones"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    field_id: Mapped[str] = mapped_column(String(64), ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    boundary_json: Mapped[dict | list] = mapped_column(JSON, default=dict)

class DeviceModel(SQLiteBase):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    field_id: Mapped[str] = mapped_column(String(64), ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="ONLINE")
    battery: Mapped[int] = mapped_column(Integer, default=100)
    tank_level: Mapped[int] = mapped_column(Integer, default=100)
    current_action: Mapped[str] = mapped_column(String(50), default="IDLE")
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class TelemetryModel(SQLiteBase):
    __tablename__ = "telemetry"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    field_id: Mapped[str] = mapped_column(String(64), index=True)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    soil_moisture: Mapped[float | None] = mapped_column(Float, nullable=True)
    soil_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    air_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    rainfall: Mapped[float | None] = mapped_column(Float, nullable=True)

class AnalysisModel(SQLiteBase):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    field_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    raw_ai_result_json: Mapped[dict] = mapped_column(JSON)
    image_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

class DecisionModel(SQLiteBase):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    analysis_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    field_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    primary_decision: Mapped[str] = mapped_column(String(50))
    risk_level: Mapped[str] = mapped_column(String(30))
    actions_json: Mapped[list] = mapped_column(JSON, default=list)
    warnings_json: Mapped[list] = mapped_column(JSON, default=list)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_decision_json: Mapped[dict] = mapped_column(JSON)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class ActionHistoryModel(SQLiteBase):
    __tablename__ = "action_history"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    field_id: Mapped[str] = mapped_column(String(64), index=True)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    decision_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    action: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30))
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    volume_ml: Mapped[float | None] = mapped_column(Float, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

# Async SQLite Engine & Session
sqlite_engine = create_async_engine(
    settings.database_url if "sqlite" in settings.database_url else "sqlite+aiosqlite:///./smart_spray.db",
    echo=False,
    connect_args={"check_same_thread": False},
)

AsyncSessionLocal = async_sessionmaker(
    bind=sqlite_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def init_sqlite_db() -> None:
    async with sqlite_engine.begin() as conn:
        await conn.run_sync(SQLiteBase.metadata.create_all)

async def get_sqlite_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
