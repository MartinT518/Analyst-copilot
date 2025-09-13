"""Tests for the ingest API endpoints."""

from uuid import UUID

from app.models import IngestJob
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_upload_file(test_client: TestClient, db_session: Session):
    """Test file upload endpoint."""
    response = test_client.post(
        "/api/v1/ingest/upload",
        files={"file": ("test.txt", b"test content", "text/plain")},
        data={"origin": "test", "sensitivity": "low"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["message"] == "File uploaded successfully and queued for processing"

    # Check if job is in the database
    job_id = UUID(data["job_id"])
    job = db_session.query(IngestJob).filter(IngestJob.id == job_id).first()
    assert job is not None
    assert job.origin == "test"
    assert job.sensitivity == "low"


def test_paste_text(test_client: TestClient, db_session: Session):
    """Test text paste endpoint."""
    response = test_client.post(
        "/api/v1/ingest/paste",
        json={
            "text": "This is a test paste.",
            "origin": "test-paste",
            "sensitivity": "medium",
            "ticket_id": "12345",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["message"] == "Text pasted successfully and queued for processing"

    # Check if job is in the database
    job_id = UUID(data["job_id"])
    job = db_session.query(IngestJob).filter(IngestJob.id == job_id).first()
    assert job is not None
    assert job.origin == "test-paste"
    assert job.sensitivity == "medium"


def test_get_job_status(test_client: TestClient, db_session: Session):
    """Test get job status endpoint."""
    # Create a dummy job with required fields
    job = IngestJob(
        source_type="test",
        origin="test",
        sensitivity="high",
        status="completed",
        uploader=1,  # Dummy user ID
    )
    db_session.add(job)
    db_session.commit()

    response = test_client.get(f"/api/v1/ingest/status/{job.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(job.id)
    assert data["status"] == "completed"


def test_list_jobs(test_client: TestClient, db_session: Session):
    """Test list jobs endpoint."""
    # Create some dummy jobs with required fields
    db_session.add(
        IngestJob(
            source_type="test", origin="test1", sensitivity="low", status="pending", uploader=1
        )
    )
    db_session.add(
        IngestJob(
            source_type="test", origin="test2", sensitivity="high", status="completed", uploader=1
        )
    )
    db_session.commit()

    response = test_client.get("/api/v1/ingest/jobs")

    assert response.status_code == 200
    data = response.json()
    assert len(data["jobs"]) == 2
