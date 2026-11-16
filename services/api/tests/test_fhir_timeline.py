from app import fhir

def test_sync_ingests_observation_condition_and_encounter(client, monkeypatch):
    fixtures = {
        "Observation": [{"resourceType":"Observation","id":"obs-1","status":"final","subject":{"reference":"Patient/fhir-1"},"code":{"text":"Heart rate"},"effectiveDateTime":"2026-01-01T10:00:00Z","meta":{"versionId":"2","lastUpdated":"2026-01-01T10:01:00Z"}}],
        "Condition": [{"resourceType":"Condition","id":"cond-1","clinicalStatus":{"text":"active"},"subject":{"reference":"Patient/fhir-1"},"code":{"text":"Synthetic demo condition"},"recordedDate":"2026-01-02","meta":{"versionId":"1"}}],
        "Encounter": [{"resourceType":"Encounter","id":"enc-1","status":"finished","subject":{"reference":"Patient/fhir-1"},"class":{"code":"AMB"},"period":{"start":"2026-01-03T08:00:00Z"},"meta":{"versionId":"3"}}]
    }
    monkeypatch.setattr(fhir, "search_resources", lambda resource_type, patient_id: fixtures[resource_type])
    monkeypatch.setattr(fhir, "upsert_demo_patient", lambda patient: {"created":False,"resource":{"resourceType":"Patient","id":"fhir-1"}})
    response = client.post("/api/v1/patients/1/fhir/sync")
    assert response.status_code == 200
    assert response.json()["imported_count"] == 3
    timeline = client.get("/api/v1/patients/1/timeline")
    assert timeline.status_code == 200
    items = timeline.json()["items"]
    assert {item["resource_type"] for item in items} == {"Observation","Condition","Encounter"}
    assert items[0]["effective_at"] is not None

def test_resource_with_different_patient_reference_is_not_ingested(client, monkeypatch):
    monkeypatch.setattr(fhir, "search_resources", lambda resource_type, patient_id: [
        {"resourceType":resource_type,"id":"wrong","subject":{"reference":"Patient/another"}}
    ])
    monkeypatch.setattr(fhir, "upsert_demo_patient", lambda patient: {"created":False,"resource":{"resourceType":"Patient","id":"fhir-1"}})
    response = client.post("/api/v1/patients/1/fhir/sync")
    assert response.status_code == 200
    assert response.json()["imported_count"] == 0

def test_effective_date_parsing():
    assert fhir._effective_date({"effectiveDateTime":"2026-01-01T10:00:00Z"}, "Observation").year == 2026
    assert fhir._effective_date({"period":{"start":"2026-01-02T08:00:00Z"}}, "Encounter").day == 2
    assert fhir._effective_date({}, "Condition") is None
