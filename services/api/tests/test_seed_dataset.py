from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import Observation, Patient
from app.seed_dataset import seed_synthetic_patients


def test_synthetic_dataset_seed_is_idempotent_and_generates_six_observations_per_patient(client):
    with SessionLocal() as db:
        first = seed_synthetic_patients(db, target_count=12, batch_size=4)
        assert first["created_patients"] == 11
        assert first["created_observations"] == 66
        assert first["current_synthetic_patient_count"] == 12

        second = seed_synthetic_patients(db, target_count=12, batch_size=4)
        assert second["created_patients"] == 0
        assert second["created_observations"] == 0

        patients = int(db.scalar(select(func.count(Patient.id)).where(Patient.external_id.like("SYN-%"))) or 0)
        observations = int(db.scalar(select(func.count(Observation.id))) or 0)
        assert patients == 12
        assert observations == 72
