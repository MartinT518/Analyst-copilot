"""Tests for the health check API endpoints."""

import pytest
from fastapi.testclient import TestClient


def test_health_check(test_client: TestClient):
    """Test health check endpoint."""
    response = test_client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy" or data["status"] == "unhealthy"
    assert "services" in data


def test_liveness_probe(test_client: TestClient):
    """Test liveness probe endpoint."""
    response = test_client.get("/health/live")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"


def test_readiness_probe(test_client: TestClient):
    """Test readiness probe endpoint."""
    response = test_client.get("/health/ready")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready" or data["status"] == "not_ready"



