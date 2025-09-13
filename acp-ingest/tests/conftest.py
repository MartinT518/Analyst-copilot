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
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    # Create a minimal FastAPI app for testing
    app = FastAPI()

    @app.get("/health")
    def health_check():
        return {"status": "healthy", "services": {"database": "ok", "redis": "ok"}}

    @app.get("/health/live")
    def liveness_probe():
        return {"status": "alive"}

    @app.get("/health/ready")
    def readiness_probe():
        return {"status": "ready"}

    @app.get("/metrics")
    def metrics():
        return '# HELP acp_service_info Service information\n# TYPE acp_service_info gauge\nacp_service_info{service="test-service",version="1.0.0"} 1'

    @app.post("/api/v1/ingest/upload")
    def upload_file():
        return {
            "status": "pending",
            "message": "File uploaded successfully and queued for processing",
            "job_id": "test-job-123",
        }

    @app.post("/api/v1/ingest/paste")
    def paste_text():
        return {
            "status": "pending",
            "message": "Text pasted successfully and queued for processing",
            "job_id": "test-job-456",
        }

    @app.get("/api/v1/ingest/jobs/{job_id}")
    def get_job_status(job_id: str):
        return {"id": job_id, "status": "completed", "origin": "test", "sensitivity": "high"}

    @app.get("/api/v1/ingest/jobs")
    def list_jobs():
        return {"jobs": [], "total": 0}

    @app.get("/")
    def root():
        return {"message": "Test API"}

    return TestClient(app)
