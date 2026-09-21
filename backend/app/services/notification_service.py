import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.sqlite import NotificationModel, gen_id, utc_now

logger = logging.getLogger("notification-service")

# Cooldown window for recurring climate/telemetry alerts (5 minutes)
CLIMATE_ALERT_COOLDOWN_SECONDS = 300

class NotificationService:
    @staticmethod
    async def create_notification(
        db: AsyncSession,
        notification_type: str,
        title: str,
        message: str,
        severity: str = "INFO",
        source: str = "SYSTEM",
        device_id: Optional[str] = "device-001",
        field_id: Optional[str] = "field-001",
        decision_id: Optional[str] = None,
        action_id: Optional[str] = None,
        stats: Optional[Dict[str, Any]] = None,
        deduplicate: bool = True,
    ) -> Optional[NotificationModel]:
        """
        Creates a new notification with deduplication for recurring climate/sensor warnings.
        """
        now = utc_now()

        # Deduplication for climate/telemetry alerts: avoid repeating identical alert within cooldown window
        if deduplicate and notification_type in ("HEATWAVE", "HEAVY_RAIN", "FLOOD_WATERLOGGING"):
            cutoff = now - timedelta(seconds=CLIMATE_ALERT_COOLDOWN_SECONDS)
            stmt = (
                select(NotificationModel)
                .where(
                    NotificationModel.type == notification_type,
                    NotificationModel.field_id == field_id,
                    NotificationModel.timestamp >= cutoff,
                )
                .order_by(desc(NotificationModel.timestamp))
                .limit(1)
            )
            res = await db.execute(stmt)
            recent = res.scalar_one_or_none()
            if recent:
                # If severity has not escalated, suppress duplicate
                if recent.severity == severity:
                    logger.info(f"[NOTIF DEDUPLICATED] Suppressed repeat alert '{notification_type}' for field '{field_id}'")
                    return recent

        notif_id = gen_id("notif-")
        notif = NotificationModel(
            id=notif_id,
            device_id=device_id,
            field_id=field_id,
            timestamp=now,
            type=notification_type,
            severity=severity,
            title=title,
            message=message,
            source=source,
            is_read=False,
            decision_id=decision_id,
            action_id=action_id,
            stats_json=stats or {},
        )
        db.add(notif)
        await db.flush()
        logger.info(f"[NOTIF CREATED] {notification_type} ({severity}) - '{title}' [{notif_id}]")
        return notif

    @staticmethod
    async def get_notifications(
        db: AsyncSession,
        field_id: Optional[str] = None,
        device_id: Optional[str] = None,
        limit: int = 50,
        unread_only: bool = False,
    ) -> List[NotificationModel]:
        stmt = select(NotificationModel)
        if field_id:
            stmt = stmt.where(NotificationModel.field_id == field_id)
        if device_id:
            stmt = stmt.where(NotificationModel.device_id == device_id)
        if unread_only:
            stmt = stmt.where(NotificationModel.is_read.is_(False))

        stmt = stmt.order_by(desc(NotificationModel.timestamp)).limit(limit)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def mark_as_read(db: AsyncSession, notification_id: str) -> bool:
        stmt = select(NotificationModel).where(NotificationModel.id == notification_id)
        res = await db.execute(stmt)
        notif = res.scalar_one_or_none()
        if not notif:
            return False
        notif.is_read = True
        await db.flush()
        return True

    @staticmethod
    async def generate_climate_alerts(
        db: AsyncSession,
        field_id: str,
        device_id: str,
        analysis: Dict[str, Any],
        sensor_data: Optional[Dict[str, Any]] = None,
        weather_data: Optional[Dict[str, Any]] = None,
    ) -> List[NotificationModel]:
        """
        Evaluate real climate risks and generate prominent warnings.
        Wording is generated strictly from real backend risk data.
        """
        created = []
        climate_risk = analysis.get("climate_risk", {})
        heat_risk = climate_risk.get("heat", 0.0)
        rain_risk = climate_risk.get("rain", 0.0) or climate_risk.get("heavy_rain", 0.0)
        flood_risk = climate_risk.get("flood", 0.0) or climate_risk.get("waterlogging", 0.0)

        # Telemetry overrides/supplements
        env = (sensor_data or {}).get("environment", {})
        temp = env.get("temperature_celsius")
        rain_detected = env.get("rain_detected", False)
        soil = (sensor_data or {}).get("soil", {})
        soil_moisture = soil.get("moisture_percent")

        # 1. Heatwave Alert
        if heat_risk >= 0.7 or (temp is not None and temp >= 38.0):
            severity = "CRITICAL" if heat_risk >= 0.85 or (temp and temp >= 42.0) else "HIGH"
            temp_str = f" ({temp:.1f}°C)" if temp is not None else ""
            n = await NotificationService.create_notification(
                db=db,
                notification_type="HEATWAVE",
                title="Heatwave Risk",
                message=f"High temperature conditions{temp_str} may stress the crop. Review irrigation requirements.",
                severity=severity,
                source="CLIMATE_ENGINE",
                device_id=device_id,
                field_id=field_id,
                stats={"heat_risk": heat_risk, "temperature_celsius": temp},
                deduplicate=True,
            )
            if n:
                created.append(n)

        # 2. Heavy Rain Alert
        if rain_risk >= 0.65 or rain_detected:
            severity = "HIGH" if rain_risk >= 0.8 or rain_detected else "MEDIUM"
            n = await NotificationService.create_notification(
                db=db,
                notification_type="HEAVY_RAIN",
                title="Heavy Rain Expected",
                message="Spraying may be delayed because rainfall could reduce treatment effectiveness.",
                severity=severity,
                source="CLIMATE_ENGINE",
                device_id=device_id,
                field_id=field_id,
                stats={"rain_risk": rain_risk, "rain_detected": rain_detected},
                deduplicate=True,
            )
            if n:
                created.append(n)

        # 3. Flood / Waterlogging Alert
        if flood_risk >= 0.7 or (soil_moisture is not None and soil_moisture >= 90.0):
            severity = "CRITICAL" if flood_risk >= 0.85 or (soil_moisture and soil_moisture >= 95.0) else "HIGH"
            moist_str = f" Soil moisture at {soil_moisture:.1f}%." if soil_moisture is not None else ""
            n = await NotificationService.create_notification(
                db=db,
                notification_type="FLOOD_WATERLOGGING",
                title="Flood / Waterlogging Risk",
                message=f"Excess water may affect crop health and irrigation decisions.{moist_str}",
                severity=severity,
                source="CLIMATE_ENGINE",
                device_id=device_id,
                field_id=field_id,
                stats={"flood_risk": flood_risk, "soil_moisture_percent": soil_moisture},
                deduplicate=True,
            )
            if n:
                created.append(n)

        return created
