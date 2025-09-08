"""Knowledge service for integrating with the ingest service knowledge base."""

import asyncio
from typing import List, Dict, Any, Optional
import httpx
import structlog
from uuid import UUID

from ..config import get_settings
from ..schemas.common_schemas import KnowledgeReference

logger = structlog.get_logger(__name__)


class KnowledgeService:
    """Service for querying the knowledge base via the ingest service."""
    
    def __init__(self):
        """Initialize the knowledge service."""
        self.settings = get_settings()
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers=self._get_headers()
        )
        self.logger = logger.bind(service="knowledge")
        
        # Performance tracking
        self.total_searches = 0
        self.successful_searches = 0
        self.failed_searches = 0
        self.total_duration = 0.0
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for ingest service requests."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"ACP-Agents/{self.settings.version}"
        }
        
        if self.settings.ingest_service_api_key:
            headers["Authorization"] = f"Bearer {self.settings.ingest_service_api_key}"
        
        return headers
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        similarity_threshold: Optional[float] = None
    ) -> List[KnowledgeReference]:
        """Search the knowledge base.
        
        Args:
            query: Search query
            limit: Maximum number of results
            filters: Optional filters for search
            similarity_threshold: Minimum similarity score
            
        Returns:
            List of knowledge references
            
        Raises:
            Exception: If search request fails
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Prepare search request
            search_data = {
                "query": query,
                "limit": limit,
                "filters": filters or {},
                "similarity_threshold": similarity_threshold or self.settings.kb_similarity_threshold
            }
            
            self.logger.info(
                "Searching knowledge base",
                query=query[:100],  # Truncate for logging
                limit=limit,
                filters=filters
            )
            
            # Make search request
            response = await self.client.post(
                f"{self.settings.ingest_service_url}/api/v1/search",
                json=search_data
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Parse results
            references = []
            for item in result.get("results", []):
                try:
                    reference = KnowledgeReference(
                        chunk_id=UUID(item["chunk_id"]),
                        source_type=item.get("source_type", "unknown"),
                        similarity_score=item.get("similarity_score", 0.0),
                        excerpt=item.get("content", "")[:500],  # Limit excerpt length
                        metadata=item.get("metadata", {})
                    )
                    references.append(reference)
                except Exception as e:
                    self.logger.warning("Failed to parse search result", error=str(e), item=item)
                    continue
            
            # Update metrics
            duration = asyncio.get_event_loop().time() - start_time
            self.total_searches += 1
            self.successful_searches += 1
            self.total_duration += duration
            
            self.logger.info(
                "Knowledge search completed",
                results_count=len(references),
                duration_seconds=duration
            )
            
            return references
            
        except httpx.HTTPStatusError as e:
            duration = asyncio.get_event_loop().time() - start_time
            self.total_searches += 1
            self.failed_searches += 1
            
            error_msg = f"Knowledge search HTTP error: {e.response.status_code} - {e.response.text}"
            self.logger.error("Knowledge search failed", error=error_msg, duration_seconds=duration)
            raise Exception(error_msg)
            
        except Exception as e:
            duration = asyncio.get_event_loop().time() - start_time
            self.total_searches += 1
            self.failed_searches += 1
            
            error_msg = f"Knowledge search failed: {str(e)}"
            self.logger.error("Knowledge search failed", error=error_msg, duration_seconds=duration)
            raise Exception(error_msg)
    
    async def get_chunk_details(self, chunk_id: UUID) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific chunk.
        
        Args:
            chunk_id: ID of the chunk to retrieve
            
        Returns:
            Chunk details or None if not found
        """
        try:
            response = await self.client.get(
                f"{self.settings.ingest_service_url}/api/v1/chunks/{chunk_id}"
            )
            
            if response.status_code == 404:
                return None
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            self.logger.error("Failed to get chunk details", chunk_id=str(chunk_id), error=str(e))
            return None
    
    async def search_by_metadata(
        self,
        metadata_filters: Dict[str, Any],
        limit: int = 10
    ) -> List[KnowledgeReference]:
        """Search knowledge base by metadata only.
        
        Args:
            metadata_filters: Metadata filters to apply
            limit: Maximum number of results
            
        Returns:
            List of knowledge references
        """
        try:
            search_data = {
                "query": "",  # Empty query for metadata-only search
                "limit": limit,
                "filters": metadata_filters,
                "metadata_only": True
            }
            
            response = await self.client.post(
                f"{self.settings.ingest_service_url}/api/v1/search",
                json=search_data
            )
            
            response.raise_for_status()
            result = response.json()
            
            references = []
            for item in result.get("results", []):
                try:
                    reference = KnowledgeReference(
                        chunk_id=UUID(item["chunk_id"]),
                        source_type=item.get("source_type", "unknown"),
                        similarity_score=1.0,  # Metadata matches are exact
                        excerpt=item.get("content", "")[:500],
                        metadata=item.get("metadata", {})
                    )
                    references.append(reference)
                except Exception as e:
                    self.logger.warning("Failed to parse metadata search result", error=str(e))
                    continue
            
            return references
            
        except Exception as e:
            error_msg = f"Metadata search failed: {str(e)}"
            self.logger.error("Metadata search failed", error=error_msg)
            raise Exception(error_msg)
    
    async def get_source_types(self) -> List[str]:
        """Get available source types in the knowledge base.
        
        Returns:
            List of source types
        """
        try:
            response = await self.client.get(
                f"{self.settings.ingest_service_url}/api/v1/sources/types"
            )
            
            response.raise_for_status()
            result = response.json()
            
            return result.get("source_types", [])
            
        except Exception as e:
            self.logger.error("Failed to get source types", error=str(e))
            return []
    
    async def get_knowledge_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge base.
        
        Returns:
            Knowledge base statistics
        """
        try:
            response = await self.client.get(
                f"{self.settings.ingest_service_url}/api/v1/stats"
            )
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            self.logger.error("Failed to get knowledge stats", error=str(e))
            return {}
    
    async def health_check(self) -> bool:
        """Check if knowledge service is healthy.
        
        Returns:
            True if service is healthy
        """
        try:
            response = await self.client.get(
                f"{self.settings.ingest_service_url}/health"
            )
            
            return response.status_code == 200
            
        except Exception as e:
            self.logger.error("Knowledge service health check failed", error=str(e))
            return False
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics.
        
        Returns:
            Dictionary of metrics
        """
        success_rate = (
            self.successful_searches / self.total_searches
            if self.total_searches > 0 else 0.0
        )
        
        average_duration = (
            self.total_duration / self.total_searches
            if self.total_searches > 0 else 0.0
        )
        
        return {
            "service": "knowledge",
            "total_searches": self.total_searches,
            "successful_searches": self.successful_searches,
            "failed_searches": self.failed_searches,
            "success_rate": success_rate,
            "average_duration_seconds": average_duration,
            "ingest_service_url": self.settings.ingest_service_url
        }
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

