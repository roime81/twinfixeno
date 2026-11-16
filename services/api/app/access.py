import os
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
    # Username matching is a local-demo compatibility switch only. In a
    # shared/production environment, bind grants to Keycloak's immutable sub.
    if os.getenv("ALLOW_USERNAME_PATIENT_GRANTS", "false").lower() in {"1", "true", "yes"} and user.get("preferred_username"):
        principal_filters.append(PatientAccessGrant.username == user["preferred_username"])
    if not principal_filters:
        raise HTTPException(status_code=404, detail="Patient not found")
    grants = list(db.scalars(select(PatientAccessGrant).where(
        PatientAccessGrant.patient_id == patient_id,
        or_(*principal_filters)
    )).all())
    if not grants:
        raise HTTPException(status_code=404, detail="Patient not found")
    if write and not any(grant.access_level == "write" for grant in grants):
        raise HTTPException(status_code=403, detail="This patient grant is read-only")
    return patient
