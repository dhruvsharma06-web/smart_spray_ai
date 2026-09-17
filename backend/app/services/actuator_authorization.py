import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.sqlite import DecisionModel, DeviceModel, FieldModel

logger = logging.getLogger("actuator-authorization")

@dataclass
class ActuatorAuthorizationResult:
    authorized: bool
    reason: str
    action: str
    decision_id: Optional[str] = None
    device_id: Optional[str] = None
    field_id: Optional[str] = None
    primary_decision: Optional[str] = None

class ActuatorAuthorizationService:
    """
    Single, authoritative safety gate for all operational actuator commands (SPRAY, IRRIGATE).
    Enforces strict invariant: NO hardware actuation without an approved, valid, unexpired DecisionResult.
    STOP and EMERGENCY_STOP bypass this service as fail-safe emergency cutoffs.
    """

    @classmethod
    async def authorize_action(
        cls,
        db: AsyncSession,
        device_id: str,
        action: str,
        decision_id: Optional[str] = None,
        preloaded_decision: Optional[Dict[str, Any]] = None,
    ) -> ActuatorAuthorizationResult:
        normalized_action = action.strip().upper()
        
        # 1. Action whitelist check
        if normalized_action not in ("SPRAY", "IRRIGATE"):
            msg = f"Operational actuation only supports SPRAY or IRRIGATE. Action '{normalized_action}' is invalid."
            logger.warning(f"[SAFETY GATE REJECT] {msg}")
            return ActuatorAuthorizationResult(
                authorized=False,
                reason=msg,
                action=normalized_action,
                device_id=device_id,
            )

        # 2. Verify device existence
        dev_stmt = select(DeviceModel).where(DeviceModel.id == device_id)
        dev_res = await db.execute(dev_stmt)
        device = dev_res.scalar_one_or_none()
        if not device:
            msg = f"Target device '{device_id}' not found in database."
            logger.warning(f"[SAFETY GATE REJECT] {msg}")
            return ActuatorAuthorizationResult(
                authorized=False,
                reason=msg,
                action=normalized_action,
                device_id=device_id,
            )

        # 3. Resolve decision record
        decision_record = None
        if decision_id:
            dec_stmt = select(DecisionModel).where(DecisionModel.id == decision_id)
            dec_res = await db.execute(dec_stmt)
            decision_record = dec_res.scalar_one_or_none()
            if not decision_record:
                msg = f"Referenced decision '{decision_id}' does not exist."
                logger.warning(f"[SAFETY GATE REJECT] {msg}")
                return ActuatorAuthorizationResult(
                    authorized=False,
                    reason=msg,
                    action=normalized_action,
                    decision_id=decision_id,
                    device_id=device_id,
                    field_id=device.field_id,
                )

        # Extract fields from DecisionModel or preloaded_decision
        if decision_record:
            dec_id = decision_record.id
            dec_field_id = decision_record.field_id
            dec_primary = str(decision_record.primary_decision).upper()
            dec_expires = decision_record.expires_at
            dec_requires_conf = bool(decision_record.requires_confirmation)
            dec_risk_level = str(decision_record.risk_level).upper()
        elif preloaded_decision:
            dec_id = preloaded_decision.get("id") or preloaded_decision.get("decision_id")
            dec_field_id = preloaded_decision.get("field_id") or device.field_id
            dec_primary = str(preloaded_decision.get("primary_decision", "")).upper()
            dec_expires = preloaded_decision.get("expires_at")
            dec_requires_conf = bool(preloaded_decision.get("requires_confirmation", False))
            dec_risk_level = str(preloaded_decision.get("risk_level", "LOW")).upper()
        else:
            msg = "Missing decision authorization reference: operational commands must supply a valid decision_id."
            logger.warning(f"[SAFETY GATE REJECT] {msg}")
            return ActuatorAuthorizationResult(
                authorized=False,
                reason=msg,
                action=normalized_action,
                device_id=device_id,
                field_id=device.field_id,
            )

        # 4. Validate field/device relationship
        if dec_field_id and str(dec_field_id) != str(device.field_id):
            msg = f"Decision field '{dec_field_id}' does not match device field '{device.field_id}'."
            logger.warning(f"[SAFETY GATE REJECT] {msg}")
            return ActuatorAuthorizationResult(
                authorized=False,
                reason=msg,
                action=normalized_action,
                decision_id=dec_id,
                device_id=device_id,
                field_id=device.field_id,
                primary_decision=dec_primary,
            )

        # 5. Validate decision expiry
        if dec_expires:
            now = datetime.now(timezone.utc)
            if dec_expires.tzinfo is None:
                dec_expires = dec_expires.replace(tzinfo=timezone.utc)
            if now > dec_expires:
                msg = f"Decision '{dec_id}' expired at {dec_expires.isoformat()}."
                logger.warning(f"[SAFETY GATE REJECT] {msg}")
                return ActuatorAuthorizationResult(
                    authorized=False,
                    reason=msg,
                    action=normalized_action,
                    decision_id=dec_id,
                    device_id=device_id,
                    field_id=device.field_id,
                    primary_decision=dec_primary,
                )

        # 6. Validate requires_confirmation == False
        if dec_requires_conf:
            msg = f"Decision '{dec_id}' requires manual agronomist confirmation. Actuation prohibited."
            logger.warning(f"[SAFETY GATE REJECT] {msg}")
            return ActuatorAuthorizationResult(
                authorized=False,
                reason=msg,
                action=normalized_action,
                decision_id=dec_id,
                device_id=device_id,
                field_id=device.field_id,
                primary_decision=dec_primary,
            )

        # 7. Validate primary_decision / action compatibility
        if normalized_action == "SPRAY":
            if dec_primary != "SPRAY":
                msg = f"Requested SPRAY incompatible with decision primary_decision='{dec_primary}'."
                logger.warning(f"[SAFETY GATE REJECT] {msg}")
                return ActuatorAuthorizationResult(
                    authorized=False,
                    reason=msg,
                    action=normalized_action,
                    decision_id=dec_id,
                    device_id=device_id,
                    field_id=device.field_id,
                    primary_decision=dec_primary,
                )
        elif normalized_action == "IRRIGATE":
            if dec_primary != "IRRIGATE":
                msg = f"Requested IRRIGATE incompatible with decision primary_decision='{dec_primary}'."
                logger.warning(f"[SAFETY GATE REJECT] {msg}")
                return ActuatorAuthorizationResult(
                    authorized=False,
                    reason=msg,
                    action=normalized_action,
                    decision_id=dec_id,
                    device_id=device_id,
                    field_id=device.field_id,
                    primary_decision=dec_primary,
                )

        # 8. All safety checks passed!
        logger.info(
            f"[SAFETY GATE APPROVED] Action '{normalized_action}' authorized for device '{device_id}' (decision: {dec_id}, primary: {dec_primary})"
        )
        return ActuatorAuthorizationResult(
            authorized=True,
            reason=f"Action '{normalized_action}' is authorized by decision '{dec_id}'.",
            action=normalized_action,
            decision_id=dec_id,
            device_id=device_id,
            field_id=device.field_id,
            primary_decision=dec_primary,
        )
