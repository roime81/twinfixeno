def test_admin_can_list_patient_access_grants(client):
    from app.main import app
    from app.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "admin-sub",
        "preferred_username": "admin",
        "roles": ["twinfixeno-admin"],
    }
    response = client.get("/api/v1/patients/1/access-grants")
    assert response.status_code == 200
    grants = response.json()
    assert {item["username"] for item in grants} >= {"demo.clinician", "demo.researcher"}
    assert {item["access_level"] for item in grants} >= {"read", "write"}


def test_non_admin_cannot_list_patient_access_grants(client):
    response = client.get("/api/v1/patients/1/access-grants")
    assert response.status_code == 403


def test_readiness_endpoint_checks_database(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"
