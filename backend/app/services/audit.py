from sqlalchemy.orm import Session
from app.models import AuditLog, User

def audit(db: Session, event_type: str, user: User | None = None, entity_type=None, entity_id=None, metadata=None):
    db.add(AuditLog(user_id=user.id if user else None, event_type=event_type, entity_type=entity_type, entity_id=str(entity_id) if entity_id else None, metadata_json=metadata))
