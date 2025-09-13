"""Tests for the search API endpoints."""

from app.models import KnowledgeChunk
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_search_knowledge(test_client: TestClient, db_session: Session):
    """Test knowledge search endpoint."""
    # Create a dummy chunk
    chunk = KnowledgeChunk(
        chunk_text="This is a test chunk for searching.",
        source_type="test",
        chunk_metadata={"origin": "test-search"},
    )
    db_session.add(chunk)
    db_session.commit()

    response = test_client.post("/api/v1/search", json={"query": "test chunk", "limit": 5})

    assert response.status_code == 200
    data = response.json()
    # This is a mock test, so we don't expect real search results
    # In a real scenario, we would mock the search service
    assert "results" in data


def test_find_similar_chunks(test_client: TestClient, db_session: Session):
    """Test find similar chunks endpoint."""
    # Create a dummy chunk
    chunk = KnowledgeChunk(
        chunk_text="This is another test chunk.",
        source_type="test",
        chunk_metadata={"origin": "test-similar"},
    )
    db_session.add(chunk)
    db_session.commit()

    response = test_client.get(f"/api/v1/search/similar/{chunk.id}")

    assert response.status_code == 200
    data = response.json()
    assert "results" in data
