from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from .models import Patient, Observation, TwinSnapshot
from .schemas import PatientOut, ObservationOut, SnapshotOut
from .seed import seed

Base.metadata.create_all(bind=engine)
seed()
app = FastAPI(title="twinfixeno API", version="0.1.0", description="Synthetic-data healthcare Digital Twin MVP")
@app.get("/health")
def health():
    return {"status":"ok","service":"twinfixeno-api"}

@app.get("/api/v1/patients", response_model=list[PatientOut])
def list_patients(db: Session = Depends(get_db)):
    return list(db.scalars(select(Patient).order_by(Patient.family_name, Patient.given_name)).all())

@app.get("/api/v1/patients/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    patient=db.get(Patient,patient_id)
    if not patient: raise HTTPException(status_code=404,detail="Patient not found")
    return patient

@app.get("/api/v1/patients/{patient_id}/observations", response_model=list[ObservationOut])
def get_observations(patient_id: int, db: Session = Depends(get_db)):
    if not db.get(Patient,patient_id): raise HTTPException(status_code=404,detail="Patient not found")
    return list(db.scalars(select(Observation).where(Observation.patient_id==patient_id).order_by(Observation.observed_at.desc())).all())

@app.get("/api/v1/patients/{patient_id}/snapshots", response_model=list[SnapshotOut])
def get_snapshots(patient_id: int, db: Session = Depends(get_db)):
    if not db.get(Patient,patient_id): raise HTTPException(status_code=404,detail="Patient not found")
    return list(db.scalars(select(TwinSnapshot).where(TwinSnapshot.patient_id==patient_id).order_by(TwinSnapshot.version.desc())).all())

@app.post("/api/v1/patients/{patient_id}/snapshots", response_model=SnapshotOut, status_code=201)
def create_snapshot(patient_id: int, db: Session = Depends(get_db)):
    if not db.get(Patient,patient_id): raise HTTPException(status_code=404,detail="Patient not found")
    version=(db.scalar(select(func.max(TwinSnapshot.version)).where(TwinSnapshot.patient_id==patient_id)) or 0)+1
    count=db.scalar(select(func.count(Observation.id)).where(Observation.patient_id==patient_id)) or 0
    item=TwinSnapshot(patient_id=patient_id,version=version,summary=f"Synthetic twin snapshot based on {count} observations. Descriptive software output only; not a clinical assessment.")
    db.add(item); db.commit(); db.refresh(item)
    return item
