"""Pytest configuration and fixtures for acp-ingest tests."""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set test environment variables
os.environ["TESTING"] = "true"
os.environ["USE_SQLITE_FOR_TESTS"] = "true"

from app.config import get_settings


@pytest.fixture(autouse=True)
def mock_auth(monkeypatch):
    """Mock authentication for all tests."""
    # Mock the auth service to bypass real authentication
    monkeypatch.setattr(
        "app.services.auth_service.auth_service.verify_token",
        lambda *a, **kw: {"sub": "test-user", "user_id": "test-user"},
    )
    monkeypatch.setattr(
        "app.services.auth_service.get_current_user",
        lambda *a, **kw: {"user_id": "test-user", "username": "test-user"},
    )


# Get test settings
settings = get_settings()

# Create test database engine
test_engine = create_engine(
    settings.get_database_url(),
    connect_args={"check_same_thread": False} if "sqlite" in settings.get_database_url() else {},
)

# Create test session factory
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a test database session."""
    # Import all models to ensure they're registered
    from app.models import Base as AppBase
    from app.resilience.dead_letter_queue import Base as DLQBase

    # Create tables for all models
    AppBase.metadata.create_all(bind=test_engine)
    DLQBase.metadata.create_all(bind=test_engine)

    # Create session
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Clean up tables
        AppBase.metadata.drop_all(bind=test_engine)
        DLQBase.metadata.drop_all(bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up test environment before each test."""
    import os
    from pathlib import Path

    # Create necessary directories (use temp directory for CI)
    import tempfile

    uploads_dir = Path(tempfile.gettempdir()) / "acp_uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # Set additional test environment variables
    os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
    os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-testing-only"
    os.environ["ENCRYPTION_KEY"] = "test-encryption-key-for-testing-only"


@pytest.fixture(scope="function")
def test_settings():
    """Get test settings."""
    return settings


@pytest.fixture(scope="function")
def test_client():
    """Create a test client for API testing."""
    # Import the real app to get all routers and middleware
    from app.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)
