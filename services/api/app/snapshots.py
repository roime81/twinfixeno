import hashlib
import json
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .models import Observation, FhirClinicalResource, TwinSnapshot, TwinSnapshotArtifact

def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)

def sha256_json(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()

def build_snapshot_payload(db: Session, patient_id: int) -> tuple[dict, dict]:
    observations = list(db.scalars(select(Observation).where(Observation.patient_id == patient_id).order_by(Observation.observed_at, Observation.id)).all())
    resources = list(db.scalars(select(FhirClinicalResource).where(FhirClinicalResource.patient_id == patient_id).order_by(FhirClinicalResource.effective_at, FhirClinicalResource.resource_type, FhirClinicalResource.fhir_id)).all())
    payload = {
        "schema": "twinfixeno.snapshot.v1",
        "patient_id": patient_id,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "observations": [{
            "id": item.id, "code": item.code, "display": item.display,
            "value": item.value, "unit": item.unit, "observed_at": item.observed_at.isoformat()
        } for item in observations],
        "fhir_resources": [{
            "resource_type": item.resource_type, "fhir_id": item.fhir_id,
            "version_id": item.version_id, "last_updated": item.last_updated.isoformat() if item.last_updated else None,
            "effective_at": item.effective_at.isoformat() if item.effective_at else None,
            "resource": item.resource_json
        } for item in resources]
    }
    observation_sources = [
        {"system": "twinfixeno-postgres", "type": "Observation", "id": str(item.id),
         "code": item.code, "observed_at": item.observed_at.isoformat(),
         "content_sha256": sha256_json({"code": item.code, "display": item.display, "value": item.value,
                                         "unit": item.unit, "observed_at": item.observed_at.isoformat()})}
        for item in observations
    ]
    fhir_sources = [
        {"system": item.source_system, "type": item.resource_type, "id": item.fhir_id,
         "version_id": item.version_id, "last_updated": item.last_updated.isoformat() if item.last_updated else None,
         "content_sha256": item.content_sha256}
        for item in resources
    ]
    provenance = {
        "captured_at": payload["captured_at"],
        "source_systems": sorted({"twinfixeno-postgres"} | ({item.source_system for item in resources})),
        "sources": observation_sources + fhir_sources,
        "observation_count": len(observations),
        "fhir_resource_count": len(resources)
    }
    return payload, provenance

def create_immutable_snapshot(db: Session, patient_id: int, created_by: str | None):
    version = (db.scalar(select(func.max(TwinSnapshot.version)).where(TwinSnapshot.patient_id == patient_id)) or 0) + 1
    payload, provenance = build_snapshot_payload(db, patient_id)
    payload_hash = sha256_json(payload)
    snapshot = TwinSnapshot(
        patient_id=patient_id, version=version,
        summary=f"Immutable snapshot v{version}: {len(payload['observations'])} observations and {len(payload['fhir_resources'])} FHIR resources.",
    )
    db.add(snapshot)
    db.flush()
    artifact = TwinSnapshotArtifact(
        snapshot_id=snapshot.id, payload=payload, provenance=provenance,
        content_sha256=payload_hash, created_by=created_by
    )
    db.add(artifact)
    db.commit()
    db.refresh(snapshot)
    db.refresh(artifact)
    return snapshot, artifact
