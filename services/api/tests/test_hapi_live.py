import os
import time
import requests
import pytest
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Patient, FhirClinicalResource
from app import fhir

pytestmark = pytest.mark.skipif(
    os.getenv("FHIR_INTEGRATION_TESTS") != "1",
    reason="Set FHIR_INTEGRATION_TESTS=1 and run a HAPI FHIR R4 server"
)

def test_live_hapi_fhir_patient_and_clinical_resource_ingestion(client):
    base = os.getenv("FHIR_BASE_URL", "http://localhost:8090/fhir").rstrip("/")
    # The workflow waits for metadata readiness; this also gives local runs a clear diagnostic.
    metadata = requests.get(base + "/metadata", timeout=10)
    metadata.raise_for_status()
    assert metadata.json().get("fhirVersion") == "4.0.1"

    with SessionLocal() as db:
        patient = db.scalar(select(Patient).where(Patient.external_id == "SYN-0001"))
        patient_result = fhir.upsert_demo_patient(patient)
        fhir_patient_id = patient_result["resource"]["id"]

    headers = {"Accept": "application/fhir+json", "Content-Type": "application/fhir+json"}
    resources = [
        {
            "resourceType": "Observation", "status": "final",
            "code": {"text": "Integration test heart rate"},
            "subject": {"reference": "Patient/" + fhir_patient_id},
            "effectiveDateTime": "2026-02-01T10:00:00Z",
            "valueQuantity": {"value": 70, "unit": "beats/minute", "system": "http://unitsofmeasure.org", "code": "/min"}
        },
        {
            "resourceType": "Condition", "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
            "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "unconfirmed"}]},
            "code": {"text": "Synthetic integration test condition"},
            "subject": {"reference": "Patient/" + fhir_patient_id},
            "recordedDate": "2026-02-02"
        },
        {
            "resourceType": "Encounter", "status": "finished",
            "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB", "display": "ambulatory"},
            "subject": {"reference": "Patient/" + fhir_patient_id},
            "period": {"start": "2026-02-03T08:00:00Z"}
        }
    ]
    for resource in resources:
        response = requests.post(base + "/" + resource["resourceType"], json=resource, headers=headers, timeout=20)
        response.raise_for_status()

    with SessionLocal() as db:
        patient = db.scalar(select(Patient).where(Patient.external_id == "SYN-0001"))
        result = fhir.sync_patient_resources(db, patient, fhir_patient_id)
        assert result["imported_count"] >= 3
        types = set(db.scalars(select(FhirClinicalResource.resource_type).where(
            FhirClinicalResource.patient_id == patient.id
        )).all())
        assert {"Observation", "Condition", "Encounter"}.issubset(types)
