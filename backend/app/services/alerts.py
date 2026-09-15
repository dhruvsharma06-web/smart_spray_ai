from sqlalchemy.orm import Session
from app.models import Alert

def create_alert(db: Session, field_id: int, alert_type: str, severity: str, message: str):
    alert = Alert(field_id=field_id, alert_type=alert_type, severity=severity, message=message)
    db.add(alert)
    return alert

def alerts_from_result(db: Session, field_id: int, analysis: dict, decision: dict):
    risk = analysis.get("climate_risk", {})
    if risk.get("heat", 0) >= .8: create_alert(db, field_id, "HIGH_HEAT_STRESS", "HIGH", "High heat stress risk detected.")
    if risk.get("drought", 0) >= .8: create_alert(db, field_id, "DROUGHT_WARNING", "HIGH", "High drought risk detected.")
    if risk.get("flood", 0) >= .8: create_alert(db, field_id, "FLOOD_WARNING", "HIGH", "High flood risk detected.")
    if risk.get("waterlogging", 0) >= .8: create_alert(db, field_id, "WATERLOGGING_WARNING", "HIGH", "High waterlogging risk detected.")
    disease = analysis.get("disease")
    if disease and disease.get("confidence", 0) >= .6: create_alert(db, field_id, "DISEASE_DETECTED", "MEDIUM", f"Possible {disease.get('name', 'disease')} detected.")
    if decision.get("primary_decision") == "DELAY_SPRAY": create_alert(db, field_id, "SPRAY_DELAYED", "MEDIUM", "Spraying was delayed by the decision engine.")
