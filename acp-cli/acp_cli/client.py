"""HTTP client for communicating with ACP services."""

import httpx
from typing import Dict, Any, Optional, Union
from pathlib import Path
import json

from .config import ServiceConfig, config_manager


class ACPClient:
    """HTTP client for ACP services."""
    
    def __init__(self, service_name: str):
        """Initialize client for a specific service.
        
        Args:
            service_name: Name of the service (ingest, agents, code-analyzer)
        """
        self.service_name = service_name
        self.config = config_manager.get_service_config(service_name)
        
        # Create HTTP client
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        
        self.client = httpx.Client(
            base_url=self.config.url,
            headers=headers,
            timeout=self.config.timeout
        )
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.client.close()
    
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make GET request.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            
        Returns:
            Response data
        """
        response = self.client.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()
    
    def post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make POST request.
        
        Args:
            endpoint: API endpoint
            data: Request data
            files: Files to upload
            
        Returns:
            Response data
        """
        if files:
            # For file uploads, don't set Content-Type header
            headers = {}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            
            response = self.client.post(endpoint, data=data, files=files, headers=headers)
        else:
            response = self.client.post(endpoint, json=data)
        
        response.raise_for_status()
        return response.json()
    
    def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make PUT request.
        
        Args:
            endpoint: API endpoint
            data: Request data
            
        Returns:
            Response data
        """
        response = self.client.put(endpoint, json=data)
        response.raise_for_status()
        return response.json()
    
    def delete(self, endpoint: str) -> Dict[str, Any]:
        """Make DELETE request.
        
        Args:
            endpoint: API endpoint
            
        Returns:
            Response data
        """
        response = self.client.delete(endpoint)
        response.raise_for_status()
        return response.json()
    
    def upload_file(self, endpoint: str, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Upload a file to the service.
        
        Args:
            endpoint: Upload endpoint
            file_path: Path to file to upload
            
        Returns:
            Response data
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(file_path, 'rb') as f:
            files = {"file": (file_path.name, f, "application/octet-stream")}
            return self.post(endpoint, files=files)
    
    def health_check(self) -> Dict[str, Any]:
        """Check service health.
        
        Returns:
            Health status
        """
        try:
            return self.get("/health")
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


class IngestClient(ACPClient):
    """Client for the ingest service."""
    
    def __init__(self):
        """Initialize ingest client."""
        super().__init__("ingest")
    
    def upload_document(self, file_path: Union[str, Path], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Upload a document for ingestion.
        
        Args:
            file_path: Path to document
            metadata: Additional metadata
            
        Returns:
            Upload response
        """
        data = {}
        if metadata:
            data["metadata"] = json.dumps(metadata)
        
        return self.upload_file("/api/v1/ingest/upload", file_path)
    
    def paste_content(self, content: str, content_type: str = "text", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Paste content for ingestion.
        
        Args:
            content: Content to ingest
            content_type: Type of content
            metadata: Additional metadata
            
        Returns:
            Paste response
        """
        data = {
            "content": content,
            "content_type": content_type
        }
        if metadata:
            data["metadata"] = metadata
        
        return self.post("/api/v1/ingest/paste", data)
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of an ingestion job.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job status
        """
        return self.get(f"/api/v1/ingest/jobs/{job_id}")
    
    def list_jobs(self, limit: int = 10, offset: int = 0) -> Dict[str, Any]:
        """List ingestion jobs.
        
        Args:
            limit: Number of jobs to return
            offset: Offset for pagination
            
        Returns:
            List of jobs
        """
        params = {"limit": limit, "offset": offset}
        return self.get("/api/v1/ingest/jobs", params)
    
    def search(self, query: str, limit: int = 10, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Search the knowledge base.
        
        Args:
            query: Search query
            limit: Number of results
            filters: Search filters
            
        Returns:
            Search results
        """
        data = {
            "query": query,
            "limit": limit
        }
        if filters:
            data["filters"] = filters
        
        return self.post("/api/v1/search", data)


class AgentsClient(ACPClient):
    """Client for the agents service."""
    
    def __init__(self):
        """Initialize agents client."""
        super().__init__("agents")
    
    def start_workflow(self, workflow_type: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Start an agent workflow.
        
        Args:
            workflow_type: Type of workflow
            input_data: Input data for workflow
            
        Returns:
            Workflow response
        """
        data = {
            "workflow_type": workflow_type,
            "input_data": input_data
        }
        return self.post("/api/v1/workflows", data)
    
    def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow status.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            Workflow status
        """
        return self.get(f"/api/v1/workflows/{workflow_id}")
    
    def list_workflows(self, limit: int = 10, offset: int = 0) -> Dict[str, Any]:
        """List workflows.
        
        Args:
            limit: Number of workflows to return
            offset: Offset for pagination
            
        Returns:
            List of workflows
        """
        params = {"limit": limit, "offset": offset}
        return self.get("/api/v1/workflows", params)


class CodeAnalyzerClient(ACPClient):
    """Client for the code analyzer service."""
    
    def __init__(self):
        """Initialize code analyzer client."""
        super().__init__("code-analyzer")
    
    def analyze_repository(self, repo_path: str, include_patterns: Optional[list] = None) -> Dict[str, Any]:
        """Analyze a code repository.
        
        Args:
            repo_path: Path to repository
            include_patterns: File patterns to include
            
        Returns:
            Analysis results
        """
        data = {
            "repo_path": repo_path
        }
        if include_patterns:
            data["include_patterns"] = include_patterns
        
        return self.post("/api/v1/analyze/repository", data)
    
    def analyze_database_schema(self, connection_string: str, schema_names: Optional[list] = None) -> Dict[str, Any]:
        """Analyze database schema.
        
        Args:
            connection_string: Database connection string
            schema_names: Schema names to analyze
            
        Returns:
            Schema analysis results
        """
        data = {
            "connection_string": connection_string
        }
        if schema_names:
            data["schema_names"] = schema_names
        
        return self.post("/api/v1/analyze/schema", data)

