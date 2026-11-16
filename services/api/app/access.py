from fastapi import HTTPException
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from .models import Patient, PatientAccessGrant

READ_ROLES = {"twinfixeno-admin", "clinician", "researcher"}
WRITE_ROLES = {"twinfixeno-admin", "clinician"}

def roles_for(user: dict) -> set[str]:
    return set(user.get("roles") or [])

def require_role(user: dict, allowed: set[str]):
    if not roles_for(user).intersection(allowed):
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
    principal_filters = []
    if user.get("sub"):
        principal_filters.append(PatientAccessGrant.user_subject == user["sub"])
    if user.get("preferred_username"):
        principal_filters.append(PatientAccessGrant.username == user["preferred_username"])
    if not principal_filters:
        raise HTTPException(status_code=404, detail="Patient not found")
    grant = db.scalar(select(PatientAccessGrant).where(
        PatientAccessGrant.patient_id == patient_id,
        or_(*principal_filters)
    ))
    if grant is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    if write and grant.access_level != "write":
        raise HTTPException(status_code=403, detail="This patient grant is read-only")
    return patient
