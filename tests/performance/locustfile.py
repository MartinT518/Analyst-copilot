"""Performance tests for ACP services using Locust."""

from locust import HttpUser, task, between
import json
import random
import string


class IngestServiceUser(HttpUser):
    """Load test user for the ingest service."""
    
    wait_time = between(1, 3)
    host = "http://localhost:8001"
    
    def on_start(self):
        """Setup for each user."""
        self.api_key = "test_api_key"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    @task(3)
    def health_check(self):
        """Test health endpoint."""
        self.client.get("/health")
    
    @task(2)
    def metrics_check(self):
        """Test metrics endpoint."""
        self.client.get("/metrics")
    
    @task(1)
    def search_documents(self):
        """Test document search."""
        search_queries = [
            "authentication",
            "user management",
            "database schema",
            "API endpoints",
            "security policies"
        ]
        
        query = random.choice(search_queries)
        payload = {
            "query": query,
            "limit": 10,
            "filters": {}
        }
        
        self.client.post(
            "/api/v1/search",
            headers=self.headers,
            json=payload
        )
    
    @task(1)
    def upload_document(self):
        """Test document upload (simulated)."""
        # Simulate a small text document upload
        document_content = ''.join(random.choices(string.ascii_letters + string.digits, k=1000))
        
        files = {
            'file': ('test_document.txt', document_content, 'text/plain')
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        self.client.post(
            "/api/v1/ingest",
            headers=headers,
            files=files
        )


class AgentsServiceUser(HttpUser):
    """Load test user for the agents service."""
    
    wait_time = between(2, 5)
    host = "http://localhost:8002"
    
    def on_start(self):
        """Setup for each user."""
        self.api_key = "test_api_key"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    @task(3)
    def health_check(self):
        """Test health endpoint."""
        self.client.get("/health")
    
    @task(2)
    def metrics_check(self):
        """Test metrics endpoint."""
        self.client.get("/metrics")
    
    @task(1)
    def clarify_request(self):
        """Test clarifier agent."""
        requests = [
            "Analyze the user authentication system",
            "Review the database schema for optimization",
            "Examine the API security implementation",
            "Evaluate the monitoring and logging setup"
        ]
        
        request_text = random.choice(requests)
        payload = {
            "request": request_text,
            "context": {}
        }
        
        self.client.post(
            "/api/v1/agents/clarify",
            headers=self.headers,
            json=payload
        )
    
    @task(1)
    def workflow_status(self):
        """Test workflow status endpoint."""
        # Generate a random workflow ID for testing
        workflow_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        
        self.client.get(
            f"/api/v1/workflows/{workflow_id}/status",
            headers=self.headers
        )


class CombinedUser(HttpUser):
    """User that tests both services."""
    
    wait_time = between(1, 4)
    
    def on_start(self):
        """Setup for each user."""
        self.api_key = "test_api_key"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Randomly choose which service to primarily use
        self.primary_service = random.choice(["ingest", "agents"])
        
        if self.primary_service == "ingest":
            self.host = "http://localhost:8001"
        else:
            self.host = "http://localhost:8002"
    
    @task(5)
    def health_check(self):
        """Test health endpoint."""
        self.client.get("/health")
    
    @task(2)
    def cross_service_health_check(self):
        """Test health endpoint of the other service."""
        if self.primary_service == "ingest":
            other_host = "http://localhost:8002"
        else:
            other_host = "http://localhost:8001"
        
        # Use a different client for cross-service calls
        with self.client.get(f"{other_host}/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Cross-service health check failed: {response.status_code}")
    
    @task(1)
    def service_specific_task(self):
        """Perform service-specific tasks."""
        if self.primary_service == "ingest":
            # Search documents
            payload = {
                "query": "test query",
                "limit": 5
            }
            self.client.post("/api/v1/search", headers=self.headers, json=payload)
        else:
            # Clarify request
            payload = {
                "request": "Test clarification request",
                "context": {}
            }
            self.client.post("/api/v1/agents/clarify", headers=self.headers, json=payload)

