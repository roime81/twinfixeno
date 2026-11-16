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


def test_username_grant_fallback_can_be_disabled(client, monkeypatch):
    from app.main import app
    from app.auth import get_current_user

    monkeypatch.setenv("ALLOW_USERNAME_PATIENT_GRANTS", "false")
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "different-immutable-subject",
        "preferred_username": "demo.clinician",
        "roles": ["clinician"],
    }
    response = client.get("/api/v1/patients/1")
    assert response.status_code == 404


def test_subject_grant_works_when_username_fallback_is_disabled(client, monkeypatch):
    from app.main import app
    from app.auth import get_current_user

    monkeypatch.setenv("ALLOW_USERNAME_PATIENT_GRANTS", "false")
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "test-subject",
        "preferred_username": "renamed.clinician",
        "roles": ["clinician"],
    }
    from app.database import SessionLocal
    from app.models import PatientAccessGrant
    with SessionLocal() as db:
        db.add(PatientAccessGrant(
            patient_id=1, user_subject="test-subject",
            username="old.username", access_level="read",
        ))
        db.commit()

    response = client.get("/api/v1/patients/1")
    assert response.status_code == 200


def test_admin_cannot_create_username_only_grant_when_disabled(client, monkeypatch):
    from app.main import app
    from app.auth import get_current_user

    monkeypatch.setenv("ALLOW_USERNAME_PATIENT_GRANTS", "false")
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "admin-subject", "preferred_username": "admin",
        "roles": ["twinfixeno-admin"],
    }
    response = client.post("/api/v1/patients/1/access-grants", json={
        "username": "some.user", "access_level": "read",
    })
    assert response.status_code == 400


def test_subject_grant_takes_precedence_over_demo_username_fallback(client, monkeypatch):
    from app.main import app
    from app.auth import get_current_user
    from app.database import SessionLocal
    from app.models import PatientAccessGrant

    monkeypatch.setenv("ALLOW_USERNAME_PATIENT_GRANTS", "true")
    with SessionLocal() as db:
        db.add(PatientAccessGrant(
            patient_id=1, user_subject="current-subject",
            username="demo.clinician", access_level="read",
        ))
        db.commit()

    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "current-subject",
        "preferred_username": "demo.clinician",
        "roles": ["clinician"],
    }
    response = client.post("/api/v1/patients/1/snapshots")
    assert response.status_code == 403


def test_admin_grant_upsert_uses_subject_not_username_or_match(client):
    from app.main import app
    from app.auth import get_current_user
    from app.database import SessionLocal
    from app.models import PatientAccessGrant
    from sqlalchemy import select

    with SessionLocal() as db:
        db.add(PatientAccessGrant(
            patient_id=1, user_subject="old-subject",
            username="person@example", access_level="read",
        ))
        db.commit()

    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "admin-subject", "preferred_username": "admin",
        "roles": ["twinfixeno-admin"],
    }
    response = client.post("/api/v1/patients/1/access-grants", json={
        "username": "person@example",
        "user_subject": "new-subject",
        "access_level": "write",
    })
    assert response.status_code == 201

    with SessionLocal() as db:
        grants = list(db.scalars(select(PatientAccessGrant).where(
            PatientAccessGrant.patient_id == 1,
        )).all())
        assert any(item.user_subject == "old-subject" and item.access_level == "read" for item in grants)
        assert any(item.user_subject == "new-subject" and item.access_level == "write" for item in grants)
