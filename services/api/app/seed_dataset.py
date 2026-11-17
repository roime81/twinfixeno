"""Deterministic, idempotent synthetic patient generator for the local demo database."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Observation, Patient

GIVEN_NAMES = (
    "Aisha", "Adam", "Amira", "Aaron", "Alya", "Amir", "Aminah", "Arif",
    "Bella", "Ben", "Chloe", "Daniel", "Danish", "Dina", "Ethan", "Farah",
    "Faris", "Hana", "Hannah", "Harith", "Ibrahim", "Iman", "Irfan", "Jasmine",
    "Jason", "Jia", "Kai", "Kavitha", "Lucas", "Liyana", "Maya", "Mei",
    "Mika", "Nadia", "Nathan", "Nina", "Nur", "Olivia", "Omar", "Priya",
    "Qistina", "Ravi", "Ryan", "Sara", "Sofia", "Suraya", "Theo", "Wei",
    "Yasmin", "Zara", "Zikri",
)
FAMILY_NAMES = (
    "Abdullah", "Ahmad", "Ali", "Aziz", "Chong", "Das", "Fernandez", "Goh",
    "Hassan", "Ibrahim", "Ismail", "Jamal", "Kaur", "Khan", "Koh", "Kumar",
    "Lee", "Lim", "Low", "Mahmud", "Menon", "Mohamed", "Murthy", "Ng",
    "Ong", "Patel", "Raman", "Rahman", "Raj", "Rao", "Salleh", "Shah",
    "Singh", "Subramaniam", "Tan", "Teo", "Thomas", "Wong", "Yap", "Yusof",
    "Zainal",
)
OBSERVATION_CODES = (
    ("8867-4", "Heart rate", "bpm"),
    ("8310-5", "Body temperature", "°C"),
    ("8480-6", "Systolic blood pressure", "mmHg"),
    ("8462-4", "Diastolic blood pressure", "mmHg"),
    ("29463-7", "Body weight", "kg"),
    ("39156-5", "BMI", "kg/m²"),
)


def _rng_for(index: int) -> random.Random:
    digest = hashlib.sha256(f"twinfixeno-synthetic-patient-v1:{index}".encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def build_synthetic_patient(index: int, anchor: datetime) -> tuple[Patient, list[tuple]]:
    rng = _rng_for(index)
    birth_start = date(1936, 1, 1)
    birth_end = date(2025, 12, 31)
    birth_days = (birth_end - birth_start).days
    birth_date = birth_start + timedelta(days=rng.randrange(birth_days + 1))
    patient = Patient(
        external_id=f"SYN-{index:05d}",
        given_name=GIVEN_NAMES[rng.randrange(len(GIVEN_NAMES))],
        family_name=FAMILY_NAMES[rng.randrange(len(FAMILY_NAMES))],
        birth_date=birth_date,
        sex=rng.choices(["female", "male", "unknown"], weights=[48, 48, 4], k=1)[0],
    )
    readings = [
        round(rng.uniform(55.0, 110.0), 1),
        round(rng.uniform(36.0, 37.7), 1),
        float(rng.randint(95, 165)),
        float(rng.randint(55, 105)),
        round(rng.uniform(42.0, 125.0), 1),
        round(rng.uniform(17.5, 42.0), 1),
    ]
    observation_rows = []
    for (code, display, unit), value in zip(OBSERVATION_CODES, readings):
        observed_at = anchor - timedelta(
            days=rng.randint(0, 90),
            hours=rng.randint(0, 23),
            minutes=rng.randint(0, 59),
        )
        observation_rows.append((code, display, value, unit, observed_at))
    return patient, observation_rows


def seed_synthetic_patients(db: Session, target_count: int = 10000, batch_size: int = 250) -> dict:
    """Ensure SYN-0001..SYN-N exist; existing IDs are never overwritten."""
    if target_count < 0 or target_count > 100000:
        raise ValueError("target_count must be between 0 and 100000")
    if batch_size < 1 or batch_size > 2000:
        raise ValueError("batch_size must be between 1 and 2000")
    if target_count == 0:
        return {"target_patient_count": 0, "created_patients": 0, "created_observations": 0}

    anchor = datetime.now(timezone.utc)
    created_patients = 0
    created_observations = 0
    for batch_start in range(1, target_count + 1, batch_size):
        batch_end = min(batch_start + batch_size - 1, target_count)
        external_ids = [f"SYN-{index:05d}" for index in range(batch_start, batch_end + 1)]
        existing = set(db.scalars(
            select(Patient.external_id).where(Patient.external_id.in_(external_ids))
        ).all())
        missing_indexes = [
            index for index in range(batch_start, batch_end + 1)
            if f"SYN-{index:05d}" not in existing
        ]
        if not missing_indexes:
            continue

        batch_patients = []
        batch_readings = []
        for index in missing_indexes:
            patient, readings = build_synthetic_patient(index, anchor)
            if index == 1:
                patient.given_name = "Alex"
                patient.family_name = "Morgan"
                patient.birth_date = date(1978, 4, 12)
                patient.sex = "female"
            batch_patients.append(patient)
            batch_readings.append(readings)

        db.add_all(batch_patients)
        db.flush()
        observation_rows = []
        for patient, readings in zip(batch_patients, batch_readings):
            for code, display, value, unit, observed_at in readings:
                observation_rows.append(Observation(
                    patient_id=patient.id,
                    code=code,
                    display=display,
                    value=value,
                    unit=unit,
                    observed_at=observed_at,
                ))
        db.add_all(observation_rows)
        db.commit()
        created_patients += len(batch_patients)
        created_observations += len(observation_rows)

    current_count = int(db.scalar(
        select(func.count(Patient.id)).where(Patient.external_id.like("SYN-%"))
    ) or 0)
    return {
        "target_patient_count": target_count,
        "created_patients": created_patients,
        "created_observations": created_observations,
        "current_synthetic_patient_count": current_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed TwinFixeno synthetic patients into the application database.")
    parser.add_argument("--count", type=int, default=10000, help="Target patient IDs SYN-0001..SYN-N.")
    parser.add_argument("--batch-size", type=int, default=250)
    args = parser.parse_args()
    with SessionLocal() as db:
        result = seed_synthetic_patients(db, target_count=args.count, batch_size=args.batch_size)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
