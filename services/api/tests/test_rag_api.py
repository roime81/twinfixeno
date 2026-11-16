def test_ai_status_exposes_local_runtime_state(client, monkeypatch):
    from app.main import rag

    expected = {
        "ollama": True,
        "qdrant": True,
        "chat_model": "qwen2.5:3b",
        "embedding_model": "nomic-embed-text",
        "chat_model_ready": True,
        "embedding_model_ready": True,
        "ready": True,
    }
    monkeypatch.setattr(rag, "ai_status", lambda: expected)
    response = client.get("/api/v1/ai/status")
    assert response.status_code == 200
    assert response.json() == expected


def test_clinician_can_index_only_with_write_grant(client, monkeypatch):
    from app.main import rag

    calls = []
    monkeypatch.setattr(rag, "index_patient", lambda db, patient_id: calls.append(patient_id) or {
        "patient_id": patient_id, "indexed": 7, "collection": "twinfixeno_clinical",
        "embedding_model": "nomic-embed-text",
    })
    response = client.post("/api/v1/patients/1/rag/index")
    assert response.status_code == 200
    assert response.json()["indexed"] == 7
    assert calls == [1]


def test_researcher_can_query_granted_patient_but_not_another_patient(client, monkeypatch):
    from datetime import date
    from app.main import app, rag
    from app.auth import get_current_user
    from app.database import SessionLocal
    from app.models import Patient

    with SessionLocal() as db:
        db.add(Patient(
            external_id="SYN-0002", given_name="Other", family_name="Patient",
            birth_date=date(1980, 1, 1), sex="unknown",
        ))
        db.commit()

    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "research-subject", "preferred_username": "demo.researcher",
        "roles": ["researcher"],
    }
    monkeypatch.setattr(rag, "answer_patient", lambda db, patient_id, question, top_k: {
        "answer": "The indexed record states a value of 72 bpm [1].",
        "answer_sha256": "a" * 64,
        "model": "qwen2.5:3b",
        "chat_model_digest": "test-chat-digest",
        "embedding_model": "nomic-embed-text",
        "embedding_model_digest": "test-embedding-digest",
        "prompt_id": "twinfixeno-evidence-assistant",
        "prompt_version": "1.0.0",
        "retrieval_version": "qdrant-patient-filter-v1",
        "index_schema_version": "1",
        "evidence_retrieved": True,
        "citation_validation": "not_automated",
        "sources": [{"rank": 1, "source_type": "Observation", "source_id": "1", "content_sha256": "b" * 64}],
    })
    allowed = client.post("/api/v1/patients/1/rag/query", json={
        "question": "Summarise the heart rate", "top_k": 5,
    })
    assert allowed.status_code == 200
    assert allowed.json()["evidence_retrieved"] is True

    denied = client.post("/api/v1/patients/2/rag/query", json={
        "question": "Summarise the record", "top_k": 5,
    })
    assert denied.status_code == 404


def test_researcher_cannot_reindex_patient_evidence(client, monkeypatch):
    from app.main import app, rag
    from app.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "research-subject", "preferred_username": "demo.researcher",
        "roles": ["researcher"],
    }
    monkeypatch.setattr(rag, "index_patient", lambda db, patient_id: {
        "patient_id": patient_id, "indexed": 1,
    })
    response = client.post("/api/v1/patients/1/rag/index")
    assert response.status_code == 403


def test_rag_query_audit_keeps_version_metadata_without_storing_answer(client, monkeypatch):
    from app.main import app, rag
    from app.auth import get_current_user
    from app.database import SessionLocal
    from app.models import AuditEvent
    from sqlalchemy import select

    monkeypatch.setattr(rag, "answer_patient", lambda db, patient_id, question, top_k: {
        "answer": "Sensitive generated answer text [1].",
        "answer_sha256": "f" * 64,
        "model": "qwen2.5:3b",
        "chat_model_digest": "chat-digest",
        "embedding_model": "nomic-embed-text",
        "embedding_model_digest": "embedding-digest",
        "prompt_id": "twinfixeno-evidence-assistant",
        "prompt_version": "1.0.0",
        "retrieval_version": "qdrant-patient-filter-v1",
        "index_schema_version": "1",
        "evidence_retrieved": True,
        "citation_validation": "not_automated",
        "sources": [{"source_type": "Observation", "source_id": "123"}],
    })
    response = client.post("/api/v1/patients/1/rag/query", json={
        "question": "Summarise recorded evidence", "top_k": 5,
    })
    assert response.status_code == 200

    with SessionLocal() as db:
        event = db.scalar(select(AuditEvent).where(AuditEvent.action == "patient.rag.query"))
        assert event is not None
        assert event.details["prompt_version"] == "1.0.0"
        assert event.details["chat_model_digest"] == "chat-digest"
        assert event.details["answer_sha256"] == "f" * 64
        assert event.details["retrieved_chunks"] == 1
        assert "answer" not in event.details
        assert "Sensitive generated answer text" not in str(event.details)
