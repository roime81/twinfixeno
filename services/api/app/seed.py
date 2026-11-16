from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select
from .database import Base, SessionLocal, engine
from .models import Patient, Observation, PatientAccessGrant

def seed():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        patient = db.scalar(select(Patient).where(Patient.external_id == "SYN-0001"))
        if patient is None:
            patient = Patient(external_id="SYN-0001", given_name="Alex", family_name="Morgan", birth_date=date(1978, 4, 12), sex="female")
            db.add(patient)
            db.flush()
            now = datetime.now(timezone.utc)
            readings = [
                ("8867-4", "Heart rate", 72, "bpm"),
                ("8310-5", "Body temperature", 36.7, "°C"),
                ("8480-6", "Systolic blood pressure", 128, "mmHg"),
                ("8462-4", "Diastolic blood pressure", 82, "mmHg"),
                ("29463-7", "Body weight", 74.2, "kg"),
                ("39156-5", "BMI", 25.1, "kg/m²"),
            ]
            for days, (code, display, value, unit) in enumerate(readings):
                db.add(Observation(patient_id=patient.id, code=code, display=display, value=value, unit=unit, observed_at=now-timedelta(days=days)))
        grant = db.scalar(select(PatientAccessGrant).where(
            PatientAccessGrant.patient_id == patient.id,
            PatientAccessGrant.username == "demo.clinician"
        ))
        if grant is None:
            db.add(PatientAccessGrant(patient_id=patient.id, username="demo.clinician", access_level="write"))
        researcher_grant = db.scalar(select(PatientAccessGrant).where(
            PatientAccessGrant.patient_id == patient.id,
            PatientAccessGrant.username == "demo.researcher"
        ))
        if researcher_grant is None:
            db.add(PatientAccessGrant(patient_id=patient.id, username="demo.researcher", access_level="read"))
        db.commit()

if __name__ == "__main__":
    seed()
