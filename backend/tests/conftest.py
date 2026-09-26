import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import Base, engine
from app.main import app
from app.models import *  # noqa: F401,F403


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


@pytest.fixture
def db_session():
    """Independent SQLAlchemy session bound to the main engine; caller manages commits."""
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()