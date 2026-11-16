from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Patient, PatientAccessGrant

READ_ROLES = {"twinfixeno-admin", "clinician", "researcher"}
WRITE_ROLES = {"twinfixeno-admin", "clinician"}

def roles_for(user: dict) -> set[str]:
    return set(user.get("roles") or [])

def require_role(user: dict, allowed: set[str]):
    roles = roles_for(user)
    if not roles.intersection(allowed):
        raise HTTPException(status_code=403, detail="Your role does not permit this operation")

def get_accessible_patient(db: Session, patient_id: int, user: dict, write: bool = False) -> Patient:
    roles = roles_for(user)
    if not roles.intersection(READ_ROLES):
        raise HTTPException(status_code=403, detail="A recognised workspace role is required")
    if write and not roles.intersection(WRITE_ROLES):
        raise HTTPException(status_code=403, detail="Read-only access")
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    if "twinfixeno-admin" in roles:
        return patient
    subject = user.get("sub")
    username = user.get("preferred_username")
    grant = db.scalar(select(PatientAccessGrant.id).where(
        PatientAccessGrant.patient_id == patient_id,
        ((PatientAccessGrant.user_subject == subject) if subject else (PatientAccessGrant.user_subject.is_(None))),
        ((PatientAccessGrant.username == username) if username else (PatientAccessGrant.username.is_(None))),
    ))
    # A grant may be bound to either a stable subject or an explicitly configured username.
    if grant is None:
        grant = db.scalar(select(PatientAccessGrant.id).where(
            PatientAccessGrant.patient_id == patient_id,
            PatientAccessGrant.user_subject == subject if subject else PatientAccessGrant.user_subject.is_(None),
            PatientAccessGrant.username == username if username else PatientAccessGrant.username.is_(None),
        ))
    if grant is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient
