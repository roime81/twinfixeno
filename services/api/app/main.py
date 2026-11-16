from datetime import date
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, or_, text, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import (
    Patient, Observation, TwinSnapshot, TwinSnapshotArtifact,
    FhirClinicalResource, PatientAccessGrant, SimulationRun, AuditEvent,
)
from .schemas import PatientOut, ObservationOut
from .seed import seed
from .auth import get_current_user
from .access import get_accessible_patient, require_role, READ_ROLES, WRITE_ROLES
from .snapshots import create_immutable_snapshot, sha256_json
from .timeline import timeline_item
from .audit import write_audit
from . import fhir

Base.metadata.create_all(bind=engine)
if engine.dialect.name == "postgresql":
    with engine.begin() as connection:
        connection.execute(text("""
        CREATE OR REPLACE FUNCTION twinfixeno_reject_snapshot_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'Twin snapshots are append-only; create a new version'; END;
        $$ LANGUAGE plpgsql;
        """))
        connection.execute(text("""
        CREATE OR REPLACE FUNCTION twinfixeno_reject_audit_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'Audit events are append-only'; END;
        $$ LANGUAGE plpgsql;
        """))
        for table in ("twin_snapshots", "twin_snapshot_artifacts"):
            trigger = f"trg_{table}_immutable"
            connection.execute(text(f"DROP TRIGGER IF EXISTS {trigger} ON {table}"))
            connection.execute(text(f"CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION twinfixeno_reject_snapshot_mutation()"))
        connection.execute(text("DROP TRIGGER IF EXISTS trg_audit_events_immutable ON audit_events"))
        connection.execute(text("CREATE TRIGGER trg_audit_events_immutable BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION twinfixeno_reject_audit_mutation()"))
seed()

app = FastAPI(
    title="twinfixeno API",
    version="0.4.0",
    description="Synthetic-data healthcare Digital Twin MVP. Not for clinical decision-making.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

class AccessGrantIn(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=255)
    user_subject: str | None = Field(default=None, min_length=1, max_length=255)
    access_level: str = Field(default="read", pattern="^(read|write)$")

class PatientIn(BaseModel):
    external_id: str = Field(min_length=5, max_length=64, pattern="^SYN-[A-Za-z0-9-]+$")
    given_name: str = Field(min_length=1, max_length=100)
    family_name: str = Field(min_length=1, max_length=100)
    birth_date: date
    sex: str = Field(default="unknown", pattern="^(female|male|unknown)$")

class SimulationIn(BaseModel):
    scenario_name: str = Field(min_length=3, max_length=120)
    baseline_observation_id: int = Field(gt=0)
    change_percent: float = Field(ge=-50, le=50)

def audit(db: Session, user: dict, action: str, request: Request, **kwargs):
    return write_audit(db, user, action, request=request, **kwargs)

@app.get("/health")
def health():
    return {"status": "ok", "service": "twinfixeno-api"}

@app.get("/health/ready")
def health_ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database is not ready") from exc
    return {"status": "ready", "service": "twinfixeno-api", "database": "connected"}

@app.get("/api/v1/me")
def who_am_i(user=Depends(get_current_user)):
    return {"subject": user["sub"], "username": user["preferred_username"], "roles": user["roles"]}

@app.get("/api/v1/integrations/fhir/status")
def fhir_status(user=Depends(get_current_user)):
    return fhir.fhir_status()

@app.get("/api/v1/patients", response_model=list[PatientOut])
def list_patients(
    request: Request,
    q: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not set(user.get("roles") or []).intersection(READ_ROLES):
        raise HTTPException(status_code=403, detail="A recognised workspace role is required")
    query = select(Patient).order_by(Patient.family_name, Patient.given_name)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        query = query.where(or_(
            Patient.external_id.ilike(pattern),
            Patient.given_name.ilike(pattern),
            Patient.family_name.ilike(pattern),
        ))
    patients = list(db.scalars(query).all())
    if "twinfixeno-admin" in (user.get("roles") or []):
        audit(db, user, "patient.registry.search", request, details={"query_present": bool(q), "result_count": len(patients)})
        return patients
    visible = []
    for patient in patients:
        try:
            get_accessible_patient(db, patient.id, user)
            visible.append(patient)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
    audit(db, user, "patient.registry.search", request, details={"query_present": bool(q), "result_count": len(visible)})
    return visible

@app.post("/api/v1/patients", status_code=201, response_model=PatientOut)
def create_patient(patient_in: PatientIn, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_role(user, {"twinfixeno-admin"})
    patient = Patient(**patient_in.model_dump())
    db.add(patient)
    try:
        db.commit()
        db.refresh(patient)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A patient with this synthetic identifier already exists") from exc
    audit(db, user, "patient.create", request, patient_id=patient.id, resource_type="Patient", resource_id=patient.external_id)
    return patient

@app.get("/api/v1/patients/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    patient = get_accessible_patient(db, patient_id, user)
    audit(db, user, "patient.read", request, patient_id=patient_id, resource_type="Patient", resource_id=patient.external_id)
    return patient

@app.get("/api/v1/patients/{patient_id}/permissions")
def get_patient_permissions(patient_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_accessible_patient(db, patient_id, user)
    roles = set(user.get("roles") or [])
    can_write = "twinfixeno-admin" in roles
    if not can_write and "clinician" in roles:
        principal_filters = []
        if user.get("sub"):
            principal_filters.append(PatientAccessGrant.user_subject == user["sub"])
        if user.get("preferred_username"):
            principal_filters.append(PatientAccessGrant.username == user["preferred_username"])
        grants = list(db.scalars(select(PatientAccessGrant).where(
            PatientAccessGrant.patient_id == patient_id, or_(*principal_filters)
        )).all()) if principal_filters else []
        can_write = any(grant.access_level == "write" for grant in grants)
    return {"can_read": True, "can_write": can_write, "can_manage_access": "twinfixeno-admin" in roles}

@app.get("/api/v1/patients/{patient_id}/observations", response_model=list[ObservationOut])
def get_observations(patient_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_accessible_patient(db, patient_id, user)
    observations = list(db.scalars(
        select(Observation).where(Observation.patient_id == patient_id).order_by(Observation.observed_at.desc())
    ).all())
    audit(db, user, "patient.observations.read", request, patient_id=patient_id, details={"count": len(observations)})
    return observations

@app.get("/api/v1/patients/{patient_id}/timeline")
def get_clinical_timeline(patient_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_accessible_patient(db, patient_id, user)
    resources = list(db.scalars(select(FhirClinicalResource).where(
        FhirClinicalResource.patient_id == patient_id
    ).order_by(FhirClinicalResource.effective_at.desc().nullslast(), FhirClinicalResource.last_updated.desc().nullslast())).all())
    audit(db, user, "patient.timeline.read", request, patient_id=patient_id, details={"resource_count": len(resources)})
    return {"patient_id": patient_id, "count": len(resources), "items": [timeline_item(item) for item in resources]}

@app.get("/api/v1/patients/{patient_id}/insights")
def get_patient_insights(patient_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    patient = get_accessible_patient(db, patient_id, user)
    observations = list(db.scalars(
        select(Observation).where(Observation.patient_id == patient_id).order_by(Observation.observed_at.desc())
    ).all())
    resources = list(db.scalars(
        select(FhirClinicalResource).where(FhirClinicalResource.patient_id == patient_id)
    ).all())
    by_display: dict[str, list[Observation]] = {}
    for item in observations:
        by_display.setdefault(item.display, []).append(item)
    summaries = []
    for display, values in by_display.items():
        latest = values[0]
        summaries.append({
            "display": display, "latest_value": latest.value, "unit": latest.unit,
            "observed_at": latest.observed_at, "record_count": len(values),
            "min_value": min(item.value for item in values), "max_value": max(item.value for item in values),
        })
    audit(db, user, "patient.context_report.generate", request, patient_id=patient_id)
    return {
        "patient": {"id": patient.id, "external_id": patient.external_id, "display_name": f"{patient.given_name} {patient.family_name}"},
        "engine": "local-deterministic-context-v1",
        "model": None,
        "observation_count": len(observations),
        "fhir_resource_count": len(resources),
        "observations": summaries,
        "resource_types": {kind: sum(1 for item in resources if item.resource_type == kind) for kind in ("Observation", "Condition", "Encounter")},
        "limitations": [
            "This is a deterministic local data summary, not an LLM-generated answer.",
            "No diagnosis, risk prediction, treatment recommendation or causal inference is performed.",
            "Only records already present in twinfixeno are included; missing data are not inferred.",
        ],
    }

@app.get("/api/v1/patients/{patient_id}/snapshots")
def get_snapshots(patient_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_accessible_patient(db, patient_id, user)
    snapshots = list(db.scalars(select(TwinSnapshot).where(
        TwinSnapshot.patient_id == patient_id
    ).order_by(TwinSnapshot.version.desc())).all())
    results = []
    for snapshot in snapshots:
        artifact = db.scalar(select(TwinSnapshotArtifact).where(TwinSnapshotArtifact.snapshot_id == snapshot.id))
        results.append({
            "id": snapshot.id, "version": snapshot.version, "summary": snapshot.summary,
            "created_at": snapshot.created_at, "content_sha256": artifact.content_sha256 if artifact else None,
            "provenance": artifact.provenance if artifact else None,
        })
    audit(db, user, "patient.snapshots.list", request, patient_id=patient_id, details={"count": len(results)})
    return results

@app.get("/api/v1/patients/{patient_id}/snapshots/{snapshot_id}")
def get_snapshot_artifact(patient_id: int, snapshot_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_accessible_patient(db, patient_id, user)
    snapshot = db.scalar(select(TwinSnapshot).where(TwinSnapshot.id == snapshot_id, TwinSnapshot.patient_id == patient_id))
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    artifact = db.scalar(select(TwinSnapshotArtifact).where(TwinSnapshotArtifact.snapshot_id == snapshot_id))
    if artifact is None:
        raise HTTPException(status_code=404, detail="Snapshot artifact not found")
    verified = sha256_json(artifact.payload) == artifact.content_sha256
    audit(db, user, "patient.snapshot.read", request, patient_id=patient_id, resource_type="TwinSnapshot", resource_id=snapshot_id, details={"integrity_verified": verified})
    return {
        "id": snapshot.id, "version": snapshot.version, "created_at": snapshot.created_at,
        "content_sha256": artifact.content_sha256, "integrity_verified": verified,
        "payload": artifact.payload, "provenance": artifact.provenance,
    }

@app.post("/api/v1/patients/{patient_id}/snapshots", status_code=201)
def create_snapshot(patient_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    patient = get_accessible_patient(db, patient_id, user, write=True)
    snapshot, artifact = create_immutable_snapshot(db, patient_id, user.get("preferred_username") or user.get("sub"))
    audit(db, user, "patient.snapshot.create", request, patient_id=patient_id, resource_type="TwinSnapshot", resource_id=snapshot.id, details={"version": snapshot.version, "content_sha256": artifact.content_sha256})
    return {
        "id": snapshot.id, "version": snapshot.version, "summary": snapshot.summary,
        "created_at": snapshot.created_at, "content_sha256": artifact.content_sha256,
        "provenance": artifact.provenance,
    }

@app.get("/api/v1/patients/{patient_id}/simulations")
def list_simulations(patient_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_accessible_patient(db, patient_id, user)
    records = list(db.scalars(select(SimulationRun).where(
        SimulationRun.patient_id == patient_id
    ).order_by(SimulationRun.created_at.desc())).all())
    audit(db, user, "patient.simulations.list", request, patient_id=patient_id, details={"count": len(records)})
    return [{
        "id": item.id, "scenario_name": item.scenario_name, "formula_id": item.formula_id,
        "inputs": item.inputs, "result": item.result, "created_by": item.created_by,
        "created_at": item.created_at,
    } for item in records]

@app.post("/api/v1/patients/{patient_id}/simulations", status_code=201)
def create_simulation(patient_id: int, simulation: SimulationIn, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_accessible_patient(db, patient_id, user, write=True)
    baseline = db.scalar(select(Observation).where(
        Observation.id == simulation.baseline_observation_id,
        Observation.patient_id == patient_id,
    ))
    if baseline is None:
        raise HTTPException(status_code=404, detail="Baseline observation not found for this patient")
    projected = round(float(baseline.value) * (1 + simulation.change_percent / 100), 4)
    inputs = {
        "baseline_observation_id": baseline.id, "metric": baseline.display,
        "baseline_value": float(baseline.value), "unit": baseline.unit,
        "change_percent": float(simulation.change_percent),
    }
    result = {
        "baseline_value": float(baseline.value), "projected_value": projected,
        "absolute_delta": round(projected - float(baseline.value), 4), "unit": baseline.unit,
        "formula": "projected = baseline × (1 + change_percent / 100)",
        "assumptions": [
            "This is a simple arithmetic scenario, not a physiological model.",
            "Only the selected value is changed; related clinical variables are not recalculated.",
            "The output is hypothetical and is not a clinical prediction or recommendation.",
        ],
        "label": "HYPOTHETICAL SCENARIO — NOT A CLINICAL PREDICTION",
    }
    record = SimulationRun(
        patient_id=patient_id, baseline_observation_id=baseline.id,
        scenario_name=simulation.scenario_name, formula_id="percentage-delta-v1",
        inputs=inputs, result=result, created_by=user.get("preferred_username") or user.get("sub"),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    audit(db, user, "patient.simulation.create", request, patient_id=patient_id, resource_type="SimulationRun", resource_id=record.id, details={"formula_id": record.formula_id})
    return {
        "id": record.id, "scenario_name": record.scenario_name, "formula_id": record.formula_id,
        "inputs": record.inputs, "result": record.result, "created_by": record.created_by,
        "created_at": record.created_at,
    }

@app.get("/api/v1/patients/{patient_id}/access-grants")
def list_access_grants(patient_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_role(user, {"twinfixeno-admin"})
    if db.get(Patient, patient_id) is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    grants = list(db.scalars(select(PatientAccessGrant).where(
        PatientAccessGrant.patient_id == patient_id
    ).order_by(PatientAccessGrant.username, PatientAccessGrant.user_subject)).all())
    return [{
        "id": item.id, "patient_id": item.patient_id, "username": item.username,
        "user_subject": item.user_subject, "access_level": item.access_level,
    } for item in grants]

@app.post("/api/v1/patients/{patient_id}/access-grants", status_code=201)
def create_access_grant(patient_id: int, grant: AccessGrantIn, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
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
        item = existing
        action = "patient.access_grant.update"
    else:
        item = PatientAccessGrant(patient_id=patient_id, username=grant.username, user_subject=grant.user_subject, access_level=grant.access_level)
        db.add(item)
        db.commit()
        db.refresh(item)
        action = "patient.access_grant.create"
    audit(db, user, action, request, patient_id=patient_id, resource_type="PatientAccessGrant", resource_id=item.id, details={"username": item.username, "access_level": item.access_level})
    return {"id": item.id, "patient_id": patient_id, "username": item.username, "user_subject": item.user_subject, "access_level": item.access_level}

@app.delete("/api/v1/patients/{patient_id}/access-grants/{grant_id}", status_code=204)
def revoke_access_grant(patient_id: int, grant_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_role(user, {"twinfixeno-admin"})
    item = db.scalar(select(PatientAccessGrant).where(PatientAccessGrant.id == grant_id, PatientAccessGrant.patient_id == patient_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Access grant not found")
    db.delete(item)
    db.commit()
    audit(db, user, "patient.access_grant.revoke", request, patient_id=patient_id, resource_type="PatientAccessGrant", resource_id=grant_id)
    return None

@app.get("/api/v1/audit/events")
def list_audit_events(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_role(user, {"twinfixeno-admin"})
    events = list(db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)).all())
    return [{
        "id": item.id, "actor_username": item.actor_username, "action": item.action,
        "patient_id": item.patient_id, "resource_type": item.resource_type,
        "resource_id": item.resource_id, "outcome": item.outcome,
        "details": item.details, "source_ip": item.source_ip, "created_at": item.created_at,
    } for item in events]

@app.post("/api/v1/patients/{patient_id}/fhir/sync")
def sync_patient_to_fhir(patient_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    patient = get_accessible_patient(db, patient_id, user, write=True)
    try:
        result = fhir.upsert_demo_patient(patient)
        resource = result.get("resource", {})
        fhir_id = resource.get("id")
        if not fhir_id:
            raise ValueError("FHIR server did not return a Patient resource id")
        published_count = fhir.publish_local_observations(db, patient, fhir_id)
        imported = fhir.sync_patient_resources(db, patient, fhir_id)
        audit(db, user, "patient.fhir.sync", request, patient_id=patient_id, resource_type="Patient", resource_id=fhir_id, details={"published_observations": published_count, "imported_resources": imported["imported_count"]})
        return {
            "patient_created": result["created"], "resource_type": "Patient", "fhir_id": fhir_id,
            "identifier": patient.external_id, "published_observation_count": published_count, **imported,
        }
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
