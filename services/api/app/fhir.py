import os
import requests

IDENTIFIER_SYSTEM = "https://twinfixeno.org/identifier/patient"

def _base_url():
    return os.getenv("FHIR_BASE_URL", "http://localhost:8090/fhir").rstrip("/")

def fhir_status():
    try:
        response = requests.get(f"{_base_url()}/metadata", headers={"Accept": "application/fhir+json"}, timeout=4)
        response.raise_for_status()
        capability = response.json()
        return {"available": True, "fhir_version": capability.get("fhirVersion"), "software": capability.get("software", {}).get("name", "HAPI FHIR"), "endpoint": _base_url()}
    except requests.RequestException as exc:
        return {"available": False, "endpoint": _base_url(), "detail": str(exc)}

def upsert_demo_patient(patient):
    """Create the synthetic demo patient in HAPI FHIR if its identifier is absent."""
    headers = {"Accept": "application/fhir+json", "Content-Type": "application/fhir+json"}
    query = requests.get(f"{_base_url()}/Patient", params={"identifier": f"{IDENTIFIER_SYSTEM}|{patient.external_id}"}, headers=headers, timeout=5)
    query.raise_for_status()
    bundle = query.json()
    if bundle.get("total", 0):
        entry = (bundle.get("entry") or [{}])[0]
        return {"created": False, "resource": entry.get("resource", {})}
    payload = {
        "resourceType": "Patient",
        "identifier": [{"system": IDENTIFIER_SYSTEM, "value": patient.external_id}],
        "active": True,
        "name": [{"use": "official", "family": patient.family_name, "given": [patient.given_name]}],
        "gender": "female" if patient.sex.lower() == "female" else "male" if patient.sex.lower() == "male" else "unknown",
        "birthDate": patient.birth_date.isoformat()
    }
    created = requests.post(f"{_base_url()}/Patient", json=payload, headers=headers, timeout=5)
    created.raise_for_status()
    return {"created": True, "resource": created.json()}

def find_patient(identifier):
    response = requests.get(f"{_base_url()}/Patient", params={"identifier": f"{IDENTIFIER_SYSTEM}|{identifier}"}, headers={"Accept": "application/fhir+json"}, timeout=5)
    response.raise_for_status()
    return response.json()
