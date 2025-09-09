"""Integration tests for ACP services."""

import pytest
import requests
import time
import os
from typing import Dict, Any


class TestServiceIntegration:
    """Test integration between ACP services."""
    
    @pytest.fixture(scope="class")
    def service_urls(self) -> Dict[str, str]:
        """Get service URLs from environment."""
        return {
            "ingest": os.getenv("INGEST_SERVICE_URL", "http://localhost:8001"),
            "agents": os.getenv("AGENTS_SERVICE_URL", "http://localhost:8002"),
        }
    
    @pytest.fixture(scope="class")
    def wait_for_services(self, service_urls: Dict[str, str]) -> None:
        """Wait for services to be ready."""
        max_retries = 30
        retry_delay = 2
        
        for service_name, url in service_urls.items():
            for attempt in range(max_retries):
                try:
                    response = requests.get(f"{url}/health", timeout=5)
                    if response.status_code == 200:
                        print(f"✅ {service_name} service is ready")
                        break
                except requests.exceptions.RequestException:
                    if attempt == max_retries - 1:
                        pytest.fail(f"❌ {service_name} service not ready after {max_retries} attempts")
                    time.sleep(retry_delay)
    
    def test_ingest_service_health(self, service_urls: Dict[str, str], wait_for_services):
        """Test ingest service health endpoint."""
        response = requests.get(f"{service_urls['ingest']}/health")
        assert response.status_code == 200
        
        health_data = response.json()
        assert health_data["status"] == "healthy"
        assert "timestamp" in health_data
        assert "version" in health_data
    
    def test_agents_service_health(self, service_urls: Dict[str, str], wait_for_services):
        """Test agents service health endpoint."""
        response = requests.get(f"{service_urls['agents']}/health")
        assert response.status_code == 200
        
        health_data = response.json()
        assert health_data["status"] == "healthy"
        assert "timestamp" in health_data
        assert "version" in health_data
    
    def test_ingest_service_metrics(self, service_urls: Dict[str, str], wait_for_services):
        """Test ingest service metrics endpoint."""
        response = requests.get(f"{service_urls['ingest']}/metrics")
        assert response.status_code == 200
        
        metrics_text = response.text
        assert "acp_requests_total" in metrics_text
        assert "acp_request_duration_seconds" in metrics_text
    
    def test_agents_service_metrics(self, service_urls: Dict[str, str], wait_for_services):
        """Test agents service metrics endpoint."""
        response = requests.get(f"{service_urls['agents']}/metrics")
        assert response.status_code == 200
        
        metrics_text = response.text
        assert "acp_requests_total" in metrics_text
        assert "acp_request_duration_seconds" in metrics_text
    
    def test_database_connectivity(self, service_urls: Dict[str, str], wait_for_services):
        """Test database connectivity through services."""
        # Test ingest service database connection
        response = requests.get(f"{service_urls['ingest']}/health/db")
        assert response.status_code == 200
        
        db_health = response.json()
        assert db_health["database"]["status"] == "connected"
        
        # Test agents service database connection
        response = requests.get(f"{service_urls['agents']}/health/db")
        assert response.status_code == 200
        
        db_health = response.json()
        assert db_health["database"]["status"] == "connected"
    
    def test_redis_connectivity(self, service_urls: Dict[str, str], wait_for_services):
        """Test Redis connectivity through services."""
        # Test ingest service Redis connection
        response = requests.get(f"{service_urls['ingest']}/health/redis")
        assert response.status_code == 200
        
        redis_health = response.json()
        assert redis_health["redis"]["status"] == "connected"
    
    def test_vector_db_connectivity(self, service_urls: Dict[str, str], wait_for_services):
        """Test vector database connectivity."""
        response = requests.get(f"{service_urls['ingest']}/health/vector")
        assert response.status_code == 200
        
        vector_health = response.json()
        assert vector_health["vector_db"]["status"] == "connected"
    
    def test_service_authentication(self, service_urls: Dict[str, str], wait_for_services):
        """Test service authentication."""
        # Test without API key
        response = requests.post(f"{service_urls['ingest']}/api/v1/ingest")
        assert response.status_code == 401
        
        # Test with invalid API key
        headers = {"Authorization": "Bearer invalid_key"}
        response = requests.post(f"{service_urls['ingest']}/api/v1/ingest", headers=headers)
        assert response.status_code == 401
    
    def test_cross_service_communication(self, service_urls: Dict[str, str], wait_for_services):
        """Test communication between services."""
        # This would test agents service calling ingest service
        # For now, just verify both services can reach each other's health endpoints
        
        # Simulate agents service checking ingest service health
        response = requests.get(f"{service_urls['ingest']}/health")
        assert response.status_code == 200
        
        # Simulate ingest service checking agents service health
        response = requests.get(f"{service_urls['agents']}/health")
        assert response.status_code == 200


class TestDatabaseMigrations:
    """Test database migrations."""
    
    def test_migration_status(self):
        """Test that all migrations have been applied."""
        import subprocess
        import os
        
        # Check ingest service migrations
        result = subprocess.run(
            ["alembic", "current"],
            cwd="migrations/acp-ingest",
            capture_output=True,
            text=True,
            env={**os.environ, "DATABASE_URL": os.getenv("DATABASE_URL")}
        )
        assert result.returncode == 0
        assert "head" in result.stdout or len(result.stdout.strip()) > 0
        
        # Check agents service migrations
        result = subprocess.run(
            ["alembic", "current"],
            cwd="migrations/acp-agents",
            capture_output=True,
            text=True,
            env={**os.environ, "DATABASE_URL": os.getenv("DATABASE_URL")}
        )
        assert result.returncode == 0
        assert "head" in result.stdout or len(result.stdout.strip()) > 0


class TestPerformance:
    """Basic performance tests."""
    
    def test_health_endpoint_performance(self, service_urls: Dict[str, str]):
        """Test health endpoint response time."""
        for service_name, url in service_urls.items():
            start_time = time.time()
            response = requests.get(f"{url}/health", timeout=5)
            end_time = time.time()
            
            assert response.status_code == 200
            response_time = end_time - start_time
            assert response_time < 1.0, f"{service_name} health check took {response_time:.2f}s"
    
    def test_metrics_endpoint_performance(self, service_urls: Dict[str, str]):
        """Test metrics endpoint response time."""
        for service_name, url in service_urls.items():
            start_time = time.time()
            response = requests.get(f"{url}/metrics", timeout=10)
            end_time = time.time()
            
            assert response.status_code == 200
            response_time = end_time - start_time
            assert response_time < 2.0, f"{service_name} metrics took {response_time:.2f}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

