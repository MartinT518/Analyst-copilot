"""Pytest configuration and fixtures for acp-ingest tests."""

import os
import tempfile
from pathlib import Path

import pytest
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings

# ---------------------------------------------------------------------------
# Global test environment setup
# ---------------------------------------------------------------------------

# Force testing mode
os.environ["TESTING"] = "true"
os.environ["USE_SQLITE_FOR_TESTS"] = "true"

# Load settings (now points to test DB or SQLite fallback)
settings = get_settings()

# Create test DB engine
test_engine = create_engine(
    settings.get_database_url(),
    connect_args={"check_same_thread": False}
    if "sqlite" in settings.get_database_url()
    else {},
)

# Session factory for tests
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def mock_auth(monkeypatch):
    """Mock authentication for all tests."""

    # Patch the method on the class
    monkeypatch.setattr(
        "app.services.auth_service.AuthService.verify_token",
        lambda self, token: {"sub": "test-user", "user_id": "test-user"},
    )

    # Patch get_current_user (if it's a function, not a method)
    monkeypatch.setattr(
        "app.services.auth_service.get_current_user",
        lambda *a, **kw: {"user_id": "test-user", "username": "test-user"},
    )


@pytest.fixture(scope="function")
def db_session():
    """Create and clean up a test database session per test."""
    # Import models so metadata is populated
    from app.models import Base as AppBase
    from app.resilience.dead_letter_queue import Base as DLQBase

    # Create tables
    AppBase.metadata.create_all(bind=test_engine)
    DLQBase.metadata.create_all(bind=test_engine)

    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop tables for clean state
        AppBase.metadata.drop_all(bind=test_engine)
        DLQBase.metadata.drop_all(bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up per-test environment variables and directories."""
    uploads_dir = Path(tempfile.gettempdir()) / "acp_uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
    os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-testing-only"
    os.environ["ENCRYPTION_KEY"] = "test-encryption-key-for-testing-only"


@pytest.fixture(scope="function")
def test_settings():
    """Return test settings."""
    return settings


@pytest.fixture(scope="function")
def test_client():
    """Provide a FastAPI test client for API testing."""
    from app.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)
