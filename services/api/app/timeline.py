from datetime import datetime
from .models import FhirClinicalResource

def timeline_item(item: FhirClinicalResource) -> dict:
    resource = item.resource_json or {}
    code = resource.get("code") or {}
    text = code.get("text")
    if not text:
        codings = code.get("coding") or []
        text = next((c.get("display") or c.get("code") for c in codings if c.get("display") or c.get("code")), None)
    if item.resource_type == "Encounter":
        text = text or ((resource.get("type") or [{}])[0] or {}).get("text") or "Encounter"
    elif item.resource_type == "Condition":
        text = text or "Condition"
    elif item.resource_type == "Observation":
        text = text or "Observation"
    return {
        "resource_type": item.resource_type,
        "resource_id": item.fhir_id,
        "version_id": item.version_id,
        "title": text or item.resource_type,
        "status": item.status,
        "effective_at": item.effective_at,
        "last_updated": item.last_updated,
        "source": item.source_system,
        "resource": resource
    }
