"""Pytest configuration and fixtures for acp-ingest tests."""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set test environment variables
os.environ["TESTING"] = "true"
os.environ["USE_SQLITE_FOR_TESTS"] = "true"

from app.config import get_settings

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


@pytest.fixture(scope="function")
def test_settings():
    """Get test settings."""
    return settings


@pytest.fixture(scope="function")
def test_client():
    """Create a test client for API testing."""
    from fastapi.testclient import TestClient

    # Import the real app to get all routers and middleware
    from app.main import app

    return TestClient(app)
