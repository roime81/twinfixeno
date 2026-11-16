import hashlib
import json
import os
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import FhirClinicalResource, Observation

IDENTIFIER_SYSTEM = "https://twinfixeno.org/identifier/patient"
OBSERVATION_IDENTIFIER_SYSTEM = "https://twinfixeno.org/identifier/observation"
SUPPORTED_RESOURCE_TYPES = ("Observation", "Condition", "Encounter")

def _base_url():
    return os.getenv("FHIR_BASE_URL", "http://localhost:8090/fhir").rstrip("/")

def _headers():
    return {"Accept": "application/fhir+json", "Content-Type": "application/fhir+json"}

def fhir_status():
    try:
        response = requests.get(f"{_base_url()}/metadata", headers=_headers(), timeout=4)
        response.raise_for_status()
        capability = response.json()
        return {"available": True, "fhir_version": capability.get("fhirVersion"), "software": capability.get("software", {}).get("name", "HAPI FHIR"), "endpoint": _base_url()}
    except requests.RequestException as exc:
        return {"available": False, "endpoint": _base_url(), "detail": str(exc)}

def find_patient(identifier):
    response = requests.get(f"{_base_url()}/Patient", params={"identifier": f"{IDENTIFIER_SYSTEM}|{identifier}"}, headers=_headers(), timeout=8)
    response.raise_for_status()
    return response.json()

def _first_resource(bundle):
    entries = bundle.get("entry") or []
    return next((entry.get("resource") for entry in entries if entry.get("resource")), None)

def upsert_demo_patient(patient):
    query = requests.get(f"{_base_url()}/Patient", params={"identifier": f"{IDENTIFIER_SYSTEM}|{patient.external_id}"}, headers=_headers(), timeout=8)
    query.raise_for_status()
    existing = _first_resource(query.json())
    if existing:
        return {"created": False, "resource": existing}
    payload = {
        "resourceType": "Patient",
        "identifier": [{"system": IDENTIFIER_SYSTEM, "value": patient.external_id}],
        "active": True,
        "name": [{"use": "official", "family": patient.family_name, "given": [patient.given_name]}],
        "gender": "female" if patient.sex.lower() == "female" else "male" if patient.sex.lower() == "male" else "unknown",
        "birthDate": patient.birth_date.isoformat()
    }
    created = requests.post(f"{_base_url()}/Patient", json=payload, headers=_headers(), timeout=8)
    created.raise_for_status()
    return {"created": True, "resource": created.json()}

def publish_local_observations(db: Session, patient, fhir_patient_id: str) -> int:
    """Idempotently publish this application's synthetic observations to HAPI FHIR."""
    unit_codes = {"bpm": "/min", "°C": "Cel", "mmHg": "mm[Hg]", "kg": "kg", "kg/m²": "kg/m2"}
    observations = list(db.scalars(
        select(Observation).where(Observation.patient_id == patient.id).order_by(Observation.id)
    ).all())
    published = 0
    for item in observations:
        identifier = f"local-observation-{item.id}"
        existing_response = requests.get(
            f"{_base_url()}/Observation",
            params={"identifier": f"{OBSERVATION_IDENTIFIER_SYSTEM}|{identifier}"},
            headers=_headers(), timeout=10,
        )
        existing_response.raise_for_status()
        existing = _first_resource(existing_response.json())
        payload = {
            "resourceType": "Observation",
            "identifier": [{"system": OBSERVATION_IDENTIFIER_SYSTEM, "value": identifier}],
            "status": "final",
            "category": [{"coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                "code": "vital-signs", "display": "Vital Signs"
            }]}],
            "code": {"coding": [{"system": "http://loinc.org", "code": item.code, "display": item.display}], "text": item.display},
            "subject": {"reference": f"Patient/{fhir_patient_id}"},
            "effectiveDateTime": item.observed_at.isoformat(),
            "valueQuantity": {
                "value": float(item.value), "unit": item.unit,
                "system": "http://unitsofmeasure.org", "code": unit_codes.get(item.unit, item.unit)
            },
        }
        if existing and existing.get("id"):
            response = requests.put(
                f"{_base_url()}/Observation/{existing['id']}",
                json={**payload, "id": existing["id"]}, headers=_headers(), timeout=10,
            )
        else:
            response = requests.post(f"{_base_url()}/Observation", json=payload, headers=_headers(), timeout=10)
        response.raise_for_status()
        published += 1
    return published

def _patient_reference(resource: dict) -> str | None:
    reference = (resource.get("subject") or {}).get("reference") or (resource.get("patient") or {}).get("reference")
    return reference if isinstance(reference, str) else None

def _effective_date(resource: dict, resource_type: str):
    raw = None
    if resource_type == "Observation":
        raw = resource.get("effectiveDateTime") or (resource.get("effectivePeriod") or {}).get("start") or resource.get("issued")
    elif resource_type == "Condition":
        raw = resource.get("onsetDateTime") or resource.get("recordedDate") or (resource.get("onsetPeriod") or {}).get("start")
    elif resource_type == "Encounter":
        raw = (resource.get("period") or {}).get("start")
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return None

def _resource_hash(resource: dict) -> str:
    canonical = json.dumps(resource, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

def search_resources(resource_type: str, patient_id: str) -> list[dict]:
    if resource_type not in SUPPORTED_RESOURCE_TYPES:
        raise ValueError("Unsupported FHIR resource type")
    url = f"{_base_url()}/{resource_type}"
    params = {"patient": f"Patient/{patient_id}", "_count": "100"}
    results = []
    completed = False
    for _ in range(20):
        response = requests.get(url, params=params, headers=_headers(), timeout=15)
        response.raise_for_status()
        bundle = response.json()
        results.extend(entry["resource"] for entry in bundle.get("entry", []) if entry.get("resource", {}).get("resourceType") == resource_type)
        next_url = next((link.get("url") for link in bundle.get("link", []) if link.get("relation") == "next"), None)
        if not next_url:
            completed = True
            break
        parsed, base = urlparse(next_url), urlparse(_base_url())
        if parsed.scheme != base.scheme or parsed.netloc != base.netloc or not parsed.path.startswith(base.path + "/"):
            raise ValueError("FHIR pagination link points outside the configured FHIR server")
        url, params = next_url, None
    if not completed:
        raise RuntimeError("FHIR search exceeded the 20-page safety limit; import was not completed")
    return results

def sync_patient_resources(db: Session, patient, fhir_patient_id: str) -> dict:
    imported = []
    for resource_type in SUPPORTED_RESOURCE_TYPES:
        for resource in search_resources(resource_type, fhir_patient_id):
            if _patient_reference(resource) != f"Patient/{fhir_patient_id}":
                continue
            fhir_id = resource.get("id")
            if not fhir_id:
                continue
            record = db.scalar(select(FhirClinicalResource).where(
                FhirClinicalResource.resource_type == resource_type,
                FhirClinicalResource.fhir_id == fhir_id
            ))
            meta = resource.get("meta") or {}
            last_updated = None
            if meta.get("lastUpdated"):
                try:
                    last_updated = datetime.fromisoformat(meta["lastUpdated"].replace("Z", "+00:00"))
                except ValueError:
                    pass
            if record is None:
                record = FhirClinicalResource(patient_id=patient.id, resource_type=resource_type, fhir_id=fhir_id, source_system="hapi-fhir")
                db.add(record)
            elif record.patient_id != patient.id:
                raise ValueError("FHIR resource identifier is already linked to a different local patient")
            record.version_id = str(meta.get("versionId")) if meta.get("versionId") is not None else None
            record.last_updated = last_updated
            record.status = resource.get("status")
            record.effective_at = _effective_date(resource, resource_type)
            record.resource_json = resource
            record.content_sha256 = _resource_hash(resource)
            imported.append({"resource_type": resource_type, "id": fhir_id, "version_id": record.version_id})
    db.commit()
    return {"imported_count": len(imported), "resources": imported}
