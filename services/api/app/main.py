from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, or_, text
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from .models import Patient, Observation, TwinSnapshot, TwinSnapshotArtifact, FhirClinicalResource, PatientAccessGrant
from .schemas import PatientOut, ObservationOut
from .seed import seed
from .auth import get_current_user
from .access import get_accessible_patient, require_role, READ_ROLES
from .snapshots import create_immutable_snapshot, sha256_json
from .timeline import timeline_item
from . import fhir

Base.metadata.create_all(bind=engine)
if engine.dialect.name == "postgresql":
    with engine.begin() as connection:
        connection.execute(text("""
        CREATE OR REPLACE FUNCTION twinfixeno_reject_snapshot_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'Twin snapshots are append-only; create a new version'; END;
        $$ LANGUAGE plpgsql;
        """))
        for table in ("twin_snapshots", "twin_snapshot_artifacts"):
            trigger = f"trg_{table}_immutable"
            connection.execute(text(f"DROP TRIGGER IF EXISTS {trigger} ON {table}"))
            connection.execute(text(f"CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION twinfixeno_reject_snapshot_mutation()"))
seed()
app = FastAPI(title="twinfixeno API", version="0.3.0", description="Synthetic-data healthcare Digital Twin MVP")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

class AccessGrantIn(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=255)
    user_subject: str | None = Field(default=None, min_length=1, max_length=255)
    access_level: str = Field(default="read", pattern="^(read|write)$")

@app.get("/health")
def health():
    return {"status": "ok", "service": "twinfixeno-api"}

@app.get("/api/v1/me")
def who_am_i(user=Depends(get_current_user)):
    return {"subject": user["sub"], "username": user["preferred_username"], "roles": user["roles"]}

@app.get("/api/v1/integrations/fhir/status")
def fhir_status(user=Depends(get_current_user)):
    return fhir.fhir_status()

@app.get("/api/v1/patients", response_model=list[PatientOut])
def list_patients(db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not set(user.get("roles") or []).intersection(READ_ROLES):
        raise HTTPException(status_code=403, detail="A recognised workspace role is required")
    patients = list(db.scalars(select(Patient).order_by(Patient.family_name, Patient.given_name)).all())
    if "twinfixeno-admin" in (user.get("roles") or []):
        return patients
    visible = []
    for patient in patients:
        try:
            get_accessible_patient(db, patient.id, user)
            visible.append(patient)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
    return visible

@app.get("/api/v1/patients/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return get_accessible_patient(db, patient_id, user)

@app.get("/api/v1/patients/{patient_id}/observations", response_model=list[ObservationOut])
def get_observations(patient_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_accessible_patient(db, patient_id, user)
    return list(db.scalars(select(Observation).where(Observation.patient_id == patient_id).order_by(Observation.observed_at.desc())).all())

@app.get("/api/v1/patients/{patient_id}/timeline")
def get_clinical_timeline(patient_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_accessible_patient(db, patient_id, user)
    resources = list(db.scalars(select(FhirClinicalResource).where(
        FhirClinicalResource.patient_id == patient_id
    ).order_by(FhirClinicalResource.effective_at.desc().nullslast(), FhirClinicalResource.last_updated.desc().nullslast())).all())
    return {"patient_id": patient_id, "count": len(resources), "items": [timeline_item(item) for item in resources]}

@app.get("/api/v1/patients/{patient_id}/snapshots")
def get_snapshots(patient_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_accessible_patient(db, patient_id, user)
    snapshots = list(db.scalars(select(TwinSnapshot).where(
        TwinSnapshot.patient_id == patient_id
    ).order_by(TwinSnapshot.version.desc())).all())
    results = []
    for snapshot in snapshots:
        artifact = db.scalar(select(TwinSnapshotArtifact).where(TwinSnapshotArtifact.snapshot_id == snapshot.id))
        results.append({"id": snapshot.id, "version": snapshot.version, "summary": snapshot.summary,
                        "created_at": snapshot.created_at, "content_sha256": artifact.content_sha256 if artifact else None,
                        "provenance": artifact.provenance if artifact else None})
    return results

@app.get("/api/v1/patients/{patient_id}/snapshots/{snapshot_id}")
def get_snapshot_artifact(patient_id: int, snapshot_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_accessible_patient(db, patient_id, user)
    snapshot = db.scalar(select(TwinSnapshot).where(TwinSnapshot.id == snapshot_id, TwinSnapshot.patient_id == patient_id))
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    artifact = db.scalar(select(TwinSnapshotArtifact).where(TwinSnapshotArtifact.snapshot_id == snapshot_id))
    if artifact is None:
        raise HTTPException(status_code=404, detail="Snapshot artifact not found")
    return {"id": snapshot.id, "version": snapshot.version, "created_at": snapshot.created_at,
            "content_sha256": artifact.content_sha256, "integrity_verified": sha256_json(artifact.payload) == artifact.content_sha256, "payload": artifact.payload, "provenance": artifact.provenance}

@app.post("/api/v1/patients/{patient_id}/snapshots", status_code=201)
def create_snapshot(patient_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_accessible_patient(db, patient_id, user, write=True)
    snapshot, artifact = create_immutable_snapshot(db, patient_id, user.get("preferred_username") or user.get("sub"))
    return {"id": snapshot.id, "version": snapshot.version, "summary": snapshot.summary,
            "created_at": snapshot.created_at, "content_sha256": artifact.content_sha256,
            "provenance": artifact.provenance}

@app.post("/api/v1/patients/{patient_id}/access-grants", status_code=201)
def create_access_grant(patient_id: int, grant: AccessGrantIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_role(user, {"twinfixeno-admin"})
    if not grant.username and not grant.user_subject:
        raise HTTPException(status_code=422, detail="Provide username or user_subject")
    if db.get(Patient, patient_id) is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    filters = []
    if grant.username:
        filters.append(PatientAccessGrant.username == grant.username)
    if grant.user_subject:
        filters.append(PatientAccessGrant.user_subject == grant.user_subject)
    existing = db.scalar(select(PatientAccessGrant).where(PatientAccessGrant.patient_id == patient_id, or_(*filters)))
    if existing:
        existing.username = grant.username or existing.username
        existing.user_subject = grant.user_subject or existing.user_subject
        existing.access_level = grant.access_level
        db.commit()
        return {"id": existing.id, "patient_id": patient_id, "username": existing.username, "user_subject": existing.user_subject, "access_level": existing.access_level}
    item = PatientAccessGrant(patient_id=patient_id, username=grant.username, user_subject=grant.user_subject, access_level=grant.access_level)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "patient_id": patient_id, "username": item.username, "user_subject": item.user_subject, "access_level": item.access_level}

@app.delete("/api/v1/patients/{patient_id}/access-grants/{grant_id}", status_code=204)
def revoke_access_grant(patient_id: int, grant_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_role(user, {"twinfixeno-admin"})
    item = db.scalar(select(PatientAccessGrant).where(PatientAccessGrant.id == grant_id, PatientAccessGrant.patient_id == patient_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Access grant not found")
    db.delete(item)
    db.commit()

@app.post("/api/v1/patients/{patient_id}/fhir/sync")
def sync_patient_to_fhir(patient_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    patient = get_accessible_patient(db, patient_id, user, write=True)
    try:
        result = fhir.upsert_demo_patient(patient)
        resource = result.get("resource", {})
        fhir_id = resource.get("id")
        if not fhir_id:
            raise ValueError("FHIR server did not return a Patient resource id")
        imported = fhir.sync_patient_resources(db, patient, fhir_id)
        return {"patient_created": result["created"], "resource_type": "Patient", "fhir_id": fhir_id,
                "identifier": patient.external_id, **imported}
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"FHIR synchronisation failed: {exc}") from exc

@app.get("/api/v1/patients/{patient_id}/fhir")
def get_patient_fhir(patient_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    patient = get_accessible_patient(db, patient_id, user)
    try:
        return fhir.find_patient(patient.external_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"FHIR server query failed: {exc}") from exc
