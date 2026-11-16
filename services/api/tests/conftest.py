import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./pytest-twinfixeno.db")
os.environ.setdefault("AUTH_REQUIRED", "false")

import pytest
from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app
from app.seed import seed
from app.auth import get_current_user

@pytest.fixture
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed()
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "test-subject", "preferred_username": "demo.clinician",
        "roles": ["clinician"]
    }
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
