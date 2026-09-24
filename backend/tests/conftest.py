import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


@pytest.fixture
def client_with_admin():
    with TestClient(app) as client:
        settings = get_settings()
        response = client.post(
            "/api/v1/auth/login",
            json={"username": settings.default_admin_username, "password": settings.default_admin_password},
        )
        token = response.json()["access_token"]
        yield client, {"Authorization": f"Bearer {token}"}
