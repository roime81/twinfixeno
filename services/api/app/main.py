from datetime import date
import hashlib
import logging
import os
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode
from sqlalchemy import select, or_, text, func, exists, false
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db
from .models import (
    Patient, Observation, TwinSnapshot, TwinSnapshotArtifact,
    FhirClinicalResource, PatientAccessGrant, SimulationRun, AuditEvent,
)
from .schemas import PatientOut, ObservationOut, PatientPage
from .auth import get_current_user
from .access import get_accessible_patient, require_role, READ_ROLES, WRITE_ROLES
from .snapshots import create_immutable_snapshot, sha256_json
from .timeline import timeline_item
from .audit import write_audit
from . import fhir, rag

logger = logging.getLogger("twinfixeno.api")

app = FastAPI(
    title="twinfixeno API",
    version="0.4.0",
    description="Synthetic-data healthcare Digital Twin MVP. Not for clinical decision-making.",
)

# Metrics and traces deliberately exclude request/response bodies, query strings,
# bearer tokens and patient names. Use route templates, not raw patient URLs.
resource = Resource.create({
    "service.name": "twinfixeno-api",
    "service.version": "0.4.0",
    "deployment.environment": os.getenv("APP_ENV", "development"),
})
trace_provider = TracerProvider(resource=resource)
otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
if otlp_endpoint:
    trace_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True))
    )
trace.set_tracer_provider(trace_provider)
http_tracer = trace.get_tracer("twinfixeno.api")
ai_tracer = trace.get_tracer("twinfixeno.ai")

RAG_QUERY_COUNTER = Counter(
    "twinfixeno_rag_queries_total",
    "Local patient evidence query operations",
    labelnames=("outcome",),
)
RAG_INDEX_COUNTER = Counter(
    "twinfixeno_rag_index_operations_total",
    "Local patient evidence indexing operations",
    labelnames=("outcome",),
)
FHIR_SYNC_COUNTER = Counter(
    "twinfixeno_fhir_sync_operations_total",
    "FHIR patient synchronisation operations",
    labelnames=("outcome",),
)
SNAPSHOT_COUNTER = Counter(
    "twinfixeno_snapshot_operations_total",
    "Twin snapshot creation operations",
    labelnames=("outcome",),
)
cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

@app.middleware("http")
async def trace_http_requests(request: Request, call_next):
    with http_tracer.start_as_current_span("http.server") as span:
        span.set_attribute("http.request.method", request.method)
        try:
            response = await call_next(request)
            route = request.scope.get("route")
            if route is not None and getattr(route, "path", None):
                span.set_attribute("http.route", route.path)
            span.set_attribute("http.response.status_code", response.status_code)
            if response.status_code >= 500:
                span.set_status(Status(StatusCode.ERROR))
            return response
        except Exception as exc:
            # Do not export exception messages: downstream HTTP/FHIR/AI exceptions
            # can contain request fragments. Keep only the error class.
            span.set_attribute("error.type", type(exc).__name__)
            span.set_status(Status(StatusCode.ERROR))
            raise

Instrumentator(
    excluded_handlers=["/metrics", "/health", "/health/ready"],
    should_group_status_codes=True,
).instrument(app).expose(app, include_in_schema=False)

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

@app.get("/api/v1/admin/dataset-status")
def get_synthetic_dataset_status(db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_role(user, {"twinfixeno-admin"})
    patient_count = int(db.scalar(select(func.count(Patient.id))) or 0)
    synthetic_patient_count = int(db.scalar(
        select(func.count(Patient.id)).where(Patient.external_id.like("SYN-%"))
    ) or 0)
    observation_count = int(db.scalar(select(func.count(Observation.id))) or 0)
    return {
        "patient_count": patient_count,
        "synthetic_patient_count": synthetic_patient_count,
        "observation_count": observation_count,
        "expected_seeded_patient_count": int(os.getenv("SEED_SYNTHETIC_PATIENTS", "0") or 0),
        "database": "postgresql" if os.getenv("DATABASE_URL", "").startswith("postgresql") else "non-postgresql",
    }


@app.get("/api/v1/patients", response_model=PatientPage)
def list_patients(
    request: Request,
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    roles = set(user.get("roles") or [])
    if not roles.intersection(READ_ROLES):
        raise HTTPException(status_code=403, detail="A recognised workspace role is required")

    filters = []
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(or_(
            Patient.external_id.ilike(pattern),
            Patient.given_name.ilike(pattern),
            Patient.family_name.ilike(pattern),
        ))

    if "twinfixeno-admin" not in roles:
        subject = user.get("sub")
        username = user.get("preferred_username")
        access_predicates = []
        subject_exists = None
        if subject:
            subject_exists = exists(select(PatientAccessGrant.id).where(
                PatientAccessGrant.patient_id == Patient.id,
                PatientAccessGrant.user_subject == subject,
            ))
            access_predicates.append(subject_exists)

        allow_username = os.getenv("ALLOW_USERNAME_PATIENT_GRANTS", "false").lower() in {"1", "true", "yes"}
        if allow_username and username:
            username_filters = [
                PatientAccessGrant.patient_id == Patient.id,
                PatientAccessGrant.username == username,
            ]
            if subject_exists is not None:
                username_filters.append(~subject_exists)
            access_predicates.append(exists(select(PatientAccessGrant.id).where(*username_filters)))

        filters.append(or_(*access_predicates) if access_predicates else false())

    total = int(db.scalar(select(func.count(Patient.id)).where(*filters)) or 0)
    patients = list(db.scalars(
        select(Patient)
        .where(*filters)
        .order_by(Patient.external_id)
        .offset(offset)
        .limit(limit)
    ).all())
    audit(db, user, "patient.registry.search", request, details={
        "query_present": bool(q and q.strip()),
        "result_count": len(patients),
        "total_count": total,
        "limit": limit,
        "offset": offset,
    })
    return PatientPage(items=patients, total=total, limit=limit, offset=offset)

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
        grant = None
        if user.get("sub"):
            grant = db.scalar(select(PatientAccessGrant).where(
                PatientAccessGrant.patient_id == patient_id,
                PatientAccessGrant.user_subject == user["sub"],
            ))
        allow_username = os.getenv("ALLOW_USERNAME_PATIENT_GRANTS", "false").lower() in {"1", "true", "yes"}
        if grant is None and allow_username and user.get("preferred_username"):
            grant = db.scalar(select(PatientAccessGrant).where(
                PatientAccessGrant.patient_id == patient_id,
                PatientAccessGrant.username == user["preferred_username"],
            ))
        can_write = bool(grant and grant.access_level == "write")
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
    try:
        snapshot, artifact = create_immutable_snapshot(db, patient_id, user.get("preferred_username") or user.get("sub"))
        SNAPSHOT_COUNTER.labels(outcome="success").inc()
    except Exception:
        SNAPSHOT_COUNTER.labels(outcome="error").inc()
        logger.exception("Twin snapshot creation failed")
        raise
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
    allow_username = os.getenv("ALLOW_USERNAME_PATIENT_GRANTS", "false").lower() in {"1", "true", "yes"}
    if grant.username and not grant.user_subject and not allow_username:
        raise HTTPException(status_code=400, detail="Username-only grants are disabled; provide the immutable Keycloak subject ID")
    if db.get(Patient, patient_id) is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    # A supplied immutable subject is the principal key; username is
    # retained only as display metadata. Use username as the lookup key only
    # for the explicit local-demo compatibility mode.
    if grant.user_subject:
        existing = db.scalar(select(PatientAccessGrant).where(
            PatientAccessGrant.patient_id == patient_id,
            PatientAccessGrant.user_subject == grant.user_subject,
        ))
    else:
        existing = db.scalar(select(PatientAccessGrant).where(
            PatientAccessGrant.patient_id == patient_id,
            PatientAccessGrant.username == grant.username,
            PatientAccessGrant.user_subject.is_(None),
        ))
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
        FHIR_SYNC_COUNTER.labels(outcome="success").inc()
        audit(db, user, "patient.fhir.sync", request, patient_id=patient_id, resource_type="Patient", resource_id=fhir_id, details={"published_observations": published_count, "imported_resources": imported["imported_count"]})
        return {
            "patient_created": result["created"], "resource_type": "Patient", "fhir_id": fhir_id,
            "identifier": patient.external_id, "published_observation_count": published_count, **imported,
        }
    except Exception as exc:
        FHIR_SYNC_COUNTER.labels(outcome="error").inc()
        logger.error("FHIR synchronisation failed", extra={"error_type": type(exc).__name__})
        db.rollback()
        raise HTTPException(status_code=502, detail="FHIR synchronisation failed; inspect API logs for diagnostic details.") from exc

@app.get("/api/v1/patients/{patient_id}/fhir")
def get_patient_fhir(patient_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    patient = get_accessible_patient(db, patient_id, user)
    try:
        return fhir.find_patient(patient.external_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"FHIR server query failed: {exc}") from exc


class RagQuestion(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=12)

@app.get('/api/v1/ai/status')
def ai_status(user=Depends(get_current_user)):
    return rag.ai_status()

@app.post('/api/v1/patients/{patient_id}/rag/index')
def rag_index(patient_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_accessible_patient(db, patient_id, user, write=True)
    try:
        with ai_tracer.start_as_current_span("ai.rag.index") as span:
            result = rag.index_patient(db, patient_id)
            span.set_attribute("ai.embedding.model", result.get("embedding_model", ""))
            span.set_attribute("ai.embedding.model_digest", result.get("embedding_model_digest") or "unavailable")
            span.set_attribute("ai.index.schema_version", result.get("index_schema_version", ""))
            span.set_attribute("ai.indexed_chunks", int(result.get("indexed", 0)))
        RAG_INDEX_COUNTER.labels(outcome="success").inc()
        audit(db, user, 'patient.rag.index', request, patient_id=patient_id, details=result)
        return result
    except Exception as exc:
        RAG_INDEX_COUNTER.labels(outcome="error").inc()
        logger.error("Local evidence indexing failed", extra={"error_type": type(exc).__name__})
        raise HTTPException(status_code=503, detail="Local evidence indexing service is unavailable; inspect API logs.") from exc

@app.post('/api/v1/patients/{patient_id}/rag/query')
def rag_query(patient_id: int, question: RagQuestion, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_accessible_patient(db, patient_id, user)
    try:
        with ai_tracer.start_as_current_span("ai.rag.query") as span:
            result = rag.answer_patient(db, patient_id, question.question, question.top_k)
            span.set_attribute("ai.model.name", result.get("model", ""))
            span.set_attribute("ai.model.digest", result.get("chat_model_digest") or "unavailable")
            span.set_attribute("ai.embedding.model", result.get("embedding_model", ""))
            span.set_attribute("ai.embedding.model_digest", result.get("embedding_model_digest") or "unavailable")
            span.set_attribute("ai.prompt.id", result.get("prompt_id", ""))
            span.set_attribute("ai.prompt.version", result.get("prompt_version", ""))
            span.set_attribute("ai.retrieval.version", result.get("retrieval_version", ""))
            span.set_attribute("ai.retrieval.count", len(result.get("sources", [])))
            span.set_attribute("ai.answer.sha256", result.get("answer_sha256", ""))
        RAG_QUERY_COUNTER.labels(outcome="success").inc()
        source_fingerprints = [
            hashlib.sha256(
                f"{item.get('source_type', '')}:{item.get('source_id', '')}".encode("utf-8")
            ).hexdigest()
            for item in result.get("sources", [])
        ]
        audit(db, user, 'patient.rag.query', request, patient_id=patient_id, details={
            "retrieved_chunks": len(result.get("sources", [])),
            "source_fingerprints": source_fingerprints,
            "prompt_id": result.get("prompt_id"),
            "prompt_version": result.get("prompt_version"),
            "retrieval_version": result.get("retrieval_version"),
            "index_schema_version": result.get("index_schema_version"),
            "chat_model": result.get("model"),
            "chat_model_digest": result.get("chat_model_digest"),
            "embedding_model": result.get("embedding_model"),
            "embedding_model_digest": result.get("embedding_model_digest"),
            "answer_sha256": result.get("answer_sha256"),
            "citation_validation": result.get("citation_validation"),
        })
        return result
    except Exception as exc:
        RAG_QUERY_COUNTER.labels(outcome="error").inc()
        logger.error("Local evidence query failed", extra={"error_type": type(exc).__name__})
        raise HTTPException(status_code=503, detail="Local evidence query service is unavailable; inspect API logs.") from exc
