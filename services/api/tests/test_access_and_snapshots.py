import pytest
from sqlalchemy import select
from app.database import SessionLocal
from app.models import TwinSnapshotArtifact
from app.snapshots import sha256_json

def test_clinician_can_access_assigned_patient(client):
    response = client.get("/api/v1/patients")
    assert response.status_code == 200
    assert response.json()[0]["external_id"] == "SYN-0001"

def test_unassigned_user_cannot_discover_patient(client):
    from app.main import app
    from app.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "unassigned", "preferred_username": "unassigned.user",
        "roles": ["clinician"]
    }
    assert client.get("/api/v1/patients/1").status_code == 404
    assert client.get("/api/v1/patients").json() == []

def test_researcher_is_read_only(client):
    from app.main import app
    from app.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "research-sub", "preferred_username": "demo.researcher",
        "roles": ["researcher"]
    }
    assert client.get("/api/v1/patients/1").status_code == 200
    assert client.post("/api/v1/patients/1/snapshots").status_code == 403

def test_admin_can_create_and_revoke_patient_grant(client):
    from app.main import app
    from app.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "admin-sub", "preferred_username": "admin",
        "roles": ["twinfixeno-admin"]
    }
    response = client.post("/api/v1/patients/1/access-grants", json={"username":"new.clinician","access_level":"write"})
    assert response.status_code == 201
    grant_id = response.json()["id"]
    assert client.delete(f"/api/v1/patients/1/access-grants/{grant_id}").status_code == 204

def test_snapshot_has_hash_and_source_provenance(client):
    response = client.post("/api/v1/patients/1/snapshots")
    assert response.status_code == 201
    result = response.json()
    assert len(result["content_sha256"]) == 64
    assert result["provenance"]["observation_count"] == 6
    with SessionLocal() as db:
        artifact = db.scalar(select(TwinSnapshotArtifact).where(TwinSnapshotArtifact.snapshot_id == result["id"]))
        assert artifact is not None
        assert sha256_json(artifact.payload) == artifact.content_sha256
    fetched = client.get(f"/api/v1/patients/1/snapshots/{result['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["content_sha256"] == result["content_sha256"]

def test_snapshot_artifact_rejects_mutation(client):
    client.post("/api/v1/patients/1/snapshots")
    with SessionLocal() as db:
        artifact = db.scalar(select(TwinSnapshotArtifact))
        artifact.payload = {"tampered": True}
        with pytest.raises(ValueError):
            db.commit()
        db.rollback()


def test_snapshot_header_is_immutable(client):
    from app.models import TwinSnapshot
    client.post("/api/v1/patients/1/snapshots")
    with SessionLocal() as db:
        snapshot = db.scalar(select(TwinSnapshot))
        snapshot.summary = "tampered"
        with pytest.raises(ValueError):
            db.commit()
        db.rollback()

def test_local_web_origin_passes_cors_preflight(client):
    response = client.options("/api/v1/patients", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization"
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
