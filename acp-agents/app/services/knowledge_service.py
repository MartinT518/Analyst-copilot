"""Knowledge service for context retrieval."""

import asyncio
from typing import List, Dict, Any, Optional
import httpx
import structlog

from ..config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class KnowledgeReference:
    """Reference to a knowledge chunk."""

    def __init__(
        self,
        chunk_id: str,
        content: str,
        source: str,
        relevance_score: float,
        metadata: Dict[str, Any],
    ):
        self.chunk_id = chunk_id
        self.content = content
        self.source = source
        self.relevance_score = relevance_score
        self.metadata = metadata


class KnowledgeService:
    """Service for retrieving knowledge from the ingest service."""

    def __init__(self):
        """Initialize knowledge service."""
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=30.0)
        self.logger = logger.bind(service="knowledge")

    async def initialize(self) -> bool:
        """Initialize the knowledge service.

        Returns:
            bool: True if successfully initialized
        """
        try:
            # Test connection to ingest service
            response = await self.client.get(f"{settings.ingest_service_url}/health")
            if response.status_code == 200:
                self.logger.info("Knowledge service initialized successfully")
                return True
            else:
                self.logger.error(
                    "Failed to connect to ingest service",
                    status_code=response.status_code,
                )
                return False
        except Exception as e:
            self.logger.error("Knowledge service initialization failed", error=str(e))
            return False

    async def search(
        self, query: str, limit: int = 10, filters: Optional[Dict[str, Any]] = None
    ) -> List[KnowledgeReference]:
        """Search knowledge base.

        Args:
            query: Search query
            limit: Maximum number of results
            filters: Optional filters

        Returns:
            List of knowledge references
        """
        try:
            # Prepare search payload
            payload = {"query": query, "limit": limit, "filters": filters or {}}

            # Add API key if configured
            headers = {}
            if settings.ingest_service_api_key:
                headers["Authorization"] = f"Bearer {settings.ingest_service_api_key}"

            # Make search request
            response = await self.client.post(
                f"{settings.ingest_service_url}/api/v1/search",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()

            # Parse response
            data = response.json()
            results = []

            for item in data.get("results", []):
                reference = KnowledgeReference(
                    chunk_id=item["chunk_id"],
                    content=item["content"],
                    source=item["source"],
                    relevance_score=item["relevance_score"],
                    metadata=item.get("metadata", {}),
                )
                results.append(reference)

            self.logger.info(
                "Knowledge search completed", query=query, results_count=len(results)
            )

            return results

        except httpx.HTTPError as e:
            self.logger.error("HTTP error in knowledge search", error=str(e))
            raise
        except Exception as e:
            self.logger.error("Unexpected error in knowledge search", error=str(e))
            raise

    async def get_chunk(self, chunk_id: str) -> Optional[KnowledgeReference]:
        """Get specific knowledge chunk.

        Args:
            chunk_id: Chunk identifier

        Returns:
            Knowledge reference or None if not found
        """
        try:
            headers = {}
            if settings.ingest_service_api_key:
                headers["Authorization"] = f"Bearer {settings.ingest_service_api_key}"

            response = await self.client.get(
                f"{settings.ingest_service_url}/api/v1/chunks/{chunk_id}",
                headers=headers,
            )

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()

            return KnowledgeReference(
                chunk_id=data["chunk_id"],
                content=data["content"],
                source=data["source"],
                relevance_score=1.0,  # Single chunk has full relevance
                metadata=data.get("metadata", {}),
            )

        except Exception as e:
            self.logger.error(
                "Failed to get knowledge chunk", chunk_id=chunk_id, error=str(e)
            )
            return None

    async def get_related_chunks(
        self, chunk_id: str, limit: int = 5
    ) -> List[KnowledgeReference]:
        """Get chunks related to a specific chunk.

        Args:
            chunk_id: Source chunk identifier
            limit: Maximum number of related chunks

        Returns:
            List of related knowledge references
        """
        try:
            # Get the source chunk first
            source_chunk = await self.get_chunk(chunk_id)
            if not source_chunk:
                return []

            # Search for related content using the source chunk's content
            return await self.search(
                query=source_chunk.content[:200],  # Use first 200 chars as query
                limit=limit,
                filters={"exclude_chunk_id": chunk_id},
            )

        except Exception as e:
            self.logger.error(
                "Failed to get related chunks", chunk_id=chunk_id, error=str(e)
            )
            return []

    async def health_check(self) -> bool:
        """Check knowledge service health.

        Returns:
            bool: True if healthy
        """
        try:
            response = await self.client.get(f"{settings.ingest_service_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def cleanup(self):
        """Cleanup knowledge service."""
        await self.client.aclose()
        self.logger.info("Knowledge service cleaned up")
