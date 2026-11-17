def test_patient_registry_search_and_admin_create(client):
    from app.main import app
    from app.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "admin-sub", "preferred_username": "admin",
        "roles": ["twinfixeno-admin"]
    }
    created = client.post("/api/v1/patients", json={
        "external_id": "SYN-0002", "given_name": "Taylor", "family_name": "Demo",
        "birth_date": "1980-01-02", "sex": "unknown"
    })
    assert created.status_code == 201
    assert created.json()["external_id"] == "SYN-0002"
    found = client.get("/api/v1/patients?q=Taylor")
    assert found.status_code == 200
    assert [item["external_id"] for item in found.json()["items"]] == ["SYN-0002"]
    assert found.json()["total"] == 1

def test_patient_permissions_reflect_patient_grant(client):
    permissions = client.get("/api/v1/patients/1/permissions")
    assert permissions.status_code == 200
    assert permissions.json() == {"can_read": True, "can_write": True, "can_manage_access": False}
    from app.main import app
    from app.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "research-sub", "preferred_username": "demo.researcher",
        "roles": ["researcher"]
    }
    read_only = client.get("/api/v1/patients/1/permissions")
    assert read_only.status_code == 200
    assert read_only.json()["can_write"] is False

def test_simulation_is_persisted_and_explicitly_hypothetical(client):
    response = client.post("/api/v1/patients/1/simulations", json={
        "scenario_name": "Illustrative heart-rate delta",
        "baseline_observation_id": 1,
        "change_percent": 10
    })
    assert response.status_code == 201
    item = response.json()
    assert item["formula_id"] == "percentage-delta-v1"
    assert item["result"]["projected_value"] == 79.2
    assert "NOT A CLINICAL PREDICTION" in item["result"]["label"]
    history = client.get("/api/v1/patients/1/simulations")
    assert history.status_code == 200
    assert history.json()[0]["id"] == item["id"]

def test_admin_can_list_grants_and_audit_events(client):
    from app.main import app
    from app.auth import get_current_user
    client.post("/api/v1/patients/1/snapshots")
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "admin-sub", "preferred_username": "admin",
        "roles": ["twinfixeno-admin"]
    }
    grants = client.get("/api/v1/patients/1/access-grants")
    assert grants.status_code == 200
    assert {grant["username"] for grant in grants.json()} >= {"demo.clinician", "demo.researcher"}
    events = client.get("/api/v1/audit/events")
    assert events.status_code == 200
    assert any(item["action"] == "patient.snapshot.create" for item in events.json())



def test_patient_registry_pagination_and_search_are_server_side(client):
    from app.main import app
    from app.auth import get_current_user
    from app.database import SessionLocal
    from app.seed_dataset import seed_synthetic_patients

    with SessionLocal() as db:
        seeded = seed_synthetic_patients(db, target_count=8, batch_size=3)
        assert seeded["current_synthetic_patient_count"] == 8

    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "admin-sub", "preferred_username": "admin",
        "roles": ["twinfixeno-admin"],
    }
    page = client.get("/api/v1/patients?limit=3&offset=2")
    assert page.status_code == 200
    assert page.json()["total"] == 8
    assert page.json()["limit"] == 3
    assert page.json()["offset"] == 2
    assert [item["external_id"] for item in page.json()["items"]] == [
        "SYN-0003", "SYN-0004", "SYN-0005",
    ]
    found = client.get("/api/v1/patients?q=SYN-0008")
    assert found.status_code == 200
    assert found.json()["total"] == 1
    assert found.json()["items"][0]["external_id"] == "SYN-0008"
