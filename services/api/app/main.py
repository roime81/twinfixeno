from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from .models import Patient, Observation, TwinSnapshot
from .schemas import PatientOut, ObservationOut, SnapshotOut
from .seed import seed
from .auth import get_current_user
from . import fhir

Base.metadata.create_all(bind=engine)
seed()
app = FastAPI(title="twinfixeno API", version="0.2.0", description="Synthetic-data healthcare Digital Twin MVP")

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
    return list(db.scalars(select(Patient).order_by(Patient.family_name, Patient.given_name)).all())

@app.get("/api/v1/patients/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient

@app.get("/api/v1/patients/{patient_id}/observations", response_model=list[ObservationOut])
def get_observations(patient_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not db.get(Patient, patient_id):
        raise HTTPException(status_code=404, detail="Patient not found")
    return list(db.scalars(select(Observation).where(Observation.patient_id == patient_id).order_by(Observation.observed_at.desc())).all())

@app.get("/api/v1/patients/{patient_id}/snapshots", response_model=list[SnapshotOut])
def get_snapshots(patient_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not db.get(Patient, patient_id):
        raise HTTPException(status_code=404, detail="Patient not found")
    return list(db.scalars(select(TwinSnapshot).where(TwinSnapshot.patient_id == patient_id).order_by(TwinSnapshot.version.desc())).all())

@app.post("/api/v1/patients/{patient_id}/snapshots", response_model=SnapshotOut, status_code=201)
def create_snapshot(patient_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not db.get(Patient, patient_id):
        raise HTTPException(status_code=404, detail="Patient not found")
    version = (db.scalar(select(func.max(TwinSnapshot.version)).where(TwinSnapshot.patient_id == patient_id)) or 0) + 1
    count = db.scalar(select(func.count(Observation.id)).where(Observation.patient_id == patient_id)) or 0
    item = TwinSnapshot(patient_id=patient_id, version=version, summary=f"Synthetic twin snapshot based on {count} observations. Descriptive software output only; not a clinical assessment.")
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@app.post("/api/v1/patients/{patient_id}/fhir/sync")
def sync_patient_to_fhir(patient_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    try:
        result = fhir.upsert_demo_patient(patient)
        resource = result.get("resource", {})
        return {"created": result["created"], "resource_type": resource.get("resourceType"), "fhir_id": resource.get("id"), "identifier": patient.external_id}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"FHIR server sync failed: {exc}") from exc

@app.get("/api/v1/patients/{patient_id}/fhir")
def get_patient_fhir(patient_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    try:
        return fhir.find_patient(patient.external_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"FHIR server query failed: {exc}") from exc
