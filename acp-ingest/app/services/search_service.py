"""Search service for semantic search and knowledge retrieval."""

import logging
import time
from typing import List, Dict, Any, Optional
from uuid import UUID
import httpx
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import KnowledgeChunk
from ..schemas import SearchResult, ChunkResponse
from .vector_service import VectorService

logger = logging.getLogger(__name__)
settings = get_settings()


class SearchService:
    """Service for semantic search and knowledge retrieval."""
    
    def __init__(self):
        self.settings = settings
        self.vector_service = VectorService()
    
    async def initialize(self):
        """Initialize the search service."""
        logger.info("Initializing search service")
        await self.vector_service.initialize()
        logger.info("Search service initialized successfully")
    
    async def cleanup(self):
        """Cleanup search service resources."""
        logger.info("Cleaning up search service")
        await self.vector_service.cleanup()
    
    async def health_check(self) -> str:
        """
        Check search service health.
        
        Returns:
            str: Health status
        """
        return await self.vector_service.health_check()
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        similarity_threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None,
        db: Session = None
    ) -> List[SearchResult]:
        """
        Perform semantic search on knowledge chunks.
        
        Args:
            query: Search query
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score
            filters: Metadata filters
            db: Database session
            
        Returns:
            List[SearchResult]: Search results
        """
        try:
            # Generate query embedding
            query_embedding = await self._generate_embedding(query)
            
            # Search similar vectors
            vector_results = await self.vector_service.search_similar(
                query_embedding=query_embedding,
                limit=limit,
                similarity_threshold=similarity_threshold,
                filters=filters
            )
            
            # Get corresponding knowledge chunks from database
            search_results = []
            for i, vector_result in enumerate(vector_results):
                # Find chunk by vector_id
                chunk = db.query(KnowledgeChunk).filter(
                    KnowledgeChunk.vector_id == vector_result['id']
                ).first()
                
                if chunk:
                    chunk_response = ChunkResponse.from_orm(chunk)
                    search_result = SearchResult(
                        chunk=chunk_response,
                        similarity_score=vector_result['similarity'],
                        rank=i + 1
                    )
                    search_results.append(search_result)
            
            logger.info(f"Search query '{query}' returned {len(search_results)} results")
            return search_results
            
        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}")
            raise
    
    async def search_by_metadata(
        self,
        filters: Dict[str, Any],
        limit: int = 100,
        db: Session = None
    ) -> List[ChunkResponse]:
        """
        Search chunks by metadata filters only.
        
        Args:
            filters: Metadata filters
            limit: Maximum number of results
            db: Database session
            
        Returns:
            List[ChunkResponse]: Matching chunks
        """
        try:
            query = db.query(KnowledgeChunk)
            
            # Apply filters
            for key, value in filters.items():
                if key == "source_type":
                    query = query.filter(KnowledgeChunk.source_type == value)
                elif key == "sensitive":
                    query = query.filter(KnowledgeChunk.sensitive == value)
                elif key == "redacted":
                    query = query.filter(KnowledgeChunk.redacted == value)
                else:
                    # JSON metadata filter
                    query = query.filter(
                        KnowledgeChunk.metadata[key].astext == str(value)
                    )
            
            chunks = query.limit(limit).all()
            return [ChunkResponse.from_orm(chunk) for chunk in chunks]
            
        except Exception as e:
            logger.error(f"Metadata search failed: {e}")
            raise
    
    async def get_chunk(self, chunk_id: UUID, db: Session) -> Optional[ChunkResponse]:
        """
        Get a specific chunk by ID.
        
        Args:
            chunk_id: Chunk identifier
            db: Database session
            
        Returns:
            Optional[ChunkResponse]: Chunk data or None if not found
        """
        chunk = db.query(KnowledgeChunk).filter(KnowledgeChunk.id == chunk_id).first()
        if chunk:
            return ChunkResponse.from_orm(chunk)
        return None
    
    async def get_related_chunks(
        self,
        chunk_id: UUID,
        limit: int = 5,
        similarity_threshold: float = 0.8,
        db: Session = None
    ) -> List[SearchResult]:
        """
        Get chunks related to a specific chunk.
        
        Args:
            chunk_id: Reference chunk ID
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score
            db: Database session
            
        Returns:
            List[SearchResult]: Related chunks
        """
        try:
            # Get the reference chunk
            reference_chunk = db.query(KnowledgeChunk).filter(
                KnowledgeChunk.id == chunk_id
            ).first()
            
            if not reference_chunk:
                return []
            
            # Generate embedding for the reference chunk text
            reference_embedding = await self._generate_embedding(reference_chunk.chunk_text)
            
            # Search for similar chunks
            vector_results = await self.vector_service.search_similar(
                query_embedding=reference_embedding,
                limit=limit + 1,  # +1 to account for the reference chunk itself
                similarity_threshold=similarity_threshold
            )
            
            # Filter out the reference chunk and convert to search results
            search_results = []
            for i, vector_result in enumerate(vector_results):
                if vector_result['id'] != reference_chunk.vector_id:
                    chunk = db.query(KnowledgeChunk).filter(
                        KnowledgeChunk.vector_id == vector_result['id']
                    ).first()
                    
                    if chunk:
                        chunk_response = ChunkResponse.from_orm(chunk)
                        search_result = SearchResult(
                            chunk=chunk_response,
                            similarity_score=vector_result['similarity'],
                            rank=len(search_results) + 1
                        )
                        search_results.append(search_result)
                        
                        if len(search_results) >= limit:
                            break
            
            return search_results
            
        except Exception as e:
            logger.error(f"Failed to get related chunks for {chunk_id}: {e}")
            raise
    
    async def get_chunks_by_source(
        self,
        source_type: str,
        origin: Optional[str] = None,
        limit: int = 100,
        db: Session = None
    ) -> List[ChunkResponse]:
        """
        Get chunks by source type and origin.
        
        Args:
            source_type: Source type filter
            origin: Origin filter
            limit: Maximum number of results
            db: Database session
            
        Returns:
            List[ChunkResponse]: Matching chunks
        """
        query = db.query(KnowledgeChunk).filter(KnowledgeChunk.source_type == source_type)
        
        if origin:
            query = query.filter(KnowledgeChunk.metadata['origin'].astext == origin)
        
        chunks = query.limit(limit).all()
        return [ChunkResponse.from_orm(chunk) for chunk in chunks]
    
    async def delete_chunks_by_source(
        self,
        source_type: str,
        origin: str,
        db: Session
    ) -> int:
        """
        Delete chunks by source type and origin.
        
        Args:
            source_type: Source type
            origin: Origin identifier
            db: Database session
            
        Returns:
            int: Number of chunks deleted
        """
        try:
            # Get chunks to delete
            chunks_to_delete = db.query(KnowledgeChunk).filter(
                KnowledgeChunk.source_type == source_type,
                KnowledgeChunk.metadata['origin'].astext == origin
            ).all()
            
            # Delete from vector database
            vector_ids = [chunk.vector_id for chunk in chunks_to_delete if chunk.vector_id]
            for vector_id in vector_ids:
                await self.vector_service.delete_vector(vector_id)
            
            # Delete from database
            deleted_count = db.query(KnowledgeChunk).filter(
                KnowledgeChunk.source_type == source_type,
                KnowledgeChunk.metadata['origin'].astext == origin
            ).delete()
            
            db.commit()
            
            logger.info(f"Deleted {deleted_count} chunks for {source_type}:{origin}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete chunks: {e}")
            db.rollback()
            raise
    
    async def get_search_suggestions(
        self,
        partial_query: str,
        limit: int = 5,
        db: Session = None
    ) -> List[str]:
        """
        Get search suggestions based on partial query.
        
        Args:
            partial_query: Partial search query
            limit: Maximum number of suggestions
            db: Database session
            
        Returns:
            List[str]: Search suggestions
        """
        try:
            # Simple implementation: get common terms from chunk metadata
            # In a more sophisticated implementation, you might use a dedicated
            # search suggestion service or analyze query patterns
            
            suggestions = []
            
            # Get chunks with titles containing the partial query
            chunks = db.query(KnowledgeChunk).filter(
                KnowledgeChunk.metadata['document_title'].astext.ilike(f'%{partial_query}%')
            ).limit(limit).all()
            
            for chunk in chunks:
                title = chunk.metadata.get('document_title', '')
                if title and title not in suggestions:
                    suggestions.append(title)
            
            return suggestions[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get search suggestions: {e}")
            return []
    
    async def get_search_stats(self, db: Session) -> Dict[str, Any]:
        """
        Get search and indexing statistics.
        
        Args:
            db: Database session
            
        Returns:
            Dict[str, Any]: Search statistics
        """
        try:
            # Get chunk counts by source type
            source_type_counts = {}
            source_types = db.query(KnowledgeChunk.source_type).distinct().all()
            
            for (source_type,) in source_types:
                count = db.query(KnowledgeChunk).filter(
                    KnowledgeChunk.source_type == source_type
                ).count()
                source_type_counts[source_type] = count
            
            # Get total chunks
            total_chunks = db.query(KnowledgeChunk).count()
            
            # Get sensitive chunks count
            sensitive_chunks = db.query(KnowledgeChunk).filter(
                KnowledgeChunk.sensitive == True
            ).count()
            
            # Get vector database stats
            vector_stats = await self.vector_service.get_collection_stats()
            
            return {
                "total_chunks": total_chunks,
                "sensitive_chunks": sensitive_chunks,
                "source_type_counts": source_type_counts,
                "vector_db_stats": vector_stats
            }
            
        except Exception as e:
            logger.error(f"Failed to get search stats: {e}")
            return {}
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text.
        
        Args:
            text: Text to embed
            
        Returns:
            List[float]: Embedding vector
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{settings.embedding_endpoint}/embeddings",
                    json={
                        "input": text,
                        "model": settings.embedding_model
                    }
                )
                response.raise_for_status()
                
                data = response.json()
                return data['data'][0]['embedding']
                
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

