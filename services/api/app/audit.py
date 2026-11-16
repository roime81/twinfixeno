from fastapi import Request
from sqlalchemy.orm import Session
from .models import AuditEvent

def write_audit(
    db: Session,
    user: dict,
    action: str,
    *,
    patient_id: int | None = None,
    resource_type: str | None = None,
    resource_id: str | int | None = None,
    outcome: str = "success",
    details: dict | None = None,
    request: Request | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_subject=user.get("sub"),
        actor_username=user.get("preferred_username"),
        action=action,
        patient_id=patient_id,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        outcome=outcome,
        details=details or {},
        source_ip=request.client.host if request and request.client else None,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
