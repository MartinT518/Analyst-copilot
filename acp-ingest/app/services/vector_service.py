"""Vector database service for managing embeddings and similarity search."""

import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple
import chromadb
from chromadb.config import Settings as ChromaSettings

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class VectorService:
    """Service for managing vector embeddings and similarity search."""
    
    def __init__(self):
        self.client = None
        self.collection = None
        self.collection_name = settings.chroma_collection_name
    
    async def initialize(self):
        """Initialize the vector database connection."""
        try:
            # Initialize Chroma client
            self.client = chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port,
                settings=ChromaSettings(
                    chroma_client_auth_provider="chromadb.auth.token.TokenAuthClientProvider",
                    chroma_client_auth_credentials="test-token"  # Configure appropriately
                )
            )
            
            # Get or create collection
            try:
                self.collection = self.client.get_collection(name=self.collection_name)
                logger.info(f"Connected to existing collection: {self.collection_name}")
            except Exception:
                # Collection doesn't exist, create it
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "ACP Knowledge Base"}
                )
                logger.info(f"Created new collection: {self.collection_name}")
            
            logger.info("Vector service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize vector service: {e}")
            raise
    
    async def cleanup(self):
        """Cleanup vector service resources."""
        logger.info("Cleaning up vector service")
        # Chroma client doesn't require explicit cleanup
    
    async def health_check(self) -> str:
        """
        Check vector database health.
        
        Returns:
            str: Health status
        """
        try:
            if self.client:
                # Try to get collection info
                collections = self.client.list_collections()
                return "healthy"
            else:
                return "unhealthy"
        except Exception as e:
            logger.error(f"Vector service health check failed: {e}")
            return "unhealthy"
    
    async def add_vector(
        self,
        embedding: List[float],
        metadata: Dict[str, Any],
        text: str
    ) -> str:
        """
        Add a vector to the collection.
        
        Args:
            embedding: Vector embedding
            metadata: Associated metadata
            text: Original text content
            
        Returns:
            str: Vector ID
        """
        try:
            vector_id = str(uuid.uuid4())
            
            # Add to collection
            self.collection.add(
                embeddings=[embedding],
                documents=[text],
                metadatas=[metadata],
                ids=[vector_id]
            )
            
            logger.debug(f"Added vector {vector_id} to collection")
            return vector_id
            
        except Exception as e:
            logger.error(f"Failed to add vector: {e}")
            raise
    
    async def add_vectors_batch(
        self,
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        texts: List[str]
    ) -> List[str]:
        """
        Add multiple vectors in batch.
        
        Args:
            embeddings: List of vector embeddings
            metadatas: List of associated metadata
            texts: List of original text content
            
        Returns:
            List[str]: List of vector IDs
        """
        try:
            vector_ids = [str(uuid.uuid4()) for _ in embeddings]
            
            # Add batch to collection
            self.collection.add(
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
                ids=vector_ids
            )
            
            logger.info(f"Added {len(vector_ids)} vectors to collection")
            return vector_ids
            
        except Exception as e:
            logger.error(f"Failed to add vectors batch: {e}")
            raise
    
    async def search_similar(
        self,
        query_embedding: List[float],
        limit: int = 10,
        similarity_threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors.
        
        Args:
            query_embedding: Query vector
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score
            filters: Metadata filters
            
        Returns:
            List[Dict[str, Any]]: Search results
        """
        try:
            # Prepare where clause for filtering
            where_clause = {}
            if filters:
                for key, value in filters.items():
                    if isinstance(value, list):
                        where_clause[key] = {"$in": value}
                    else:
                        where_clause[key] = {"$eq": value}
            
            # Perform search
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where=where_clause if where_clause else None,
                include=["documents", "metadatas", "distances"]
            )
            
            # Process results
            search_results = []
            if results['ids'] and results['ids'][0]:
                for i, vector_id in enumerate(results['ids'][0]):
                    # Convert distance to similarity score (assuming cosine distance)
                    distance = results['distances'][0][i]
                    similarity = 1 - distance  # Convert distance to similarity
                    
                    if similarity >= similarity_threshold:
                        search_results.append({
                            'id': vector_id,
                            'similarity': similarity,
                            'text': results['documents'][0][i],
                            'metadata': results['metadatas'][0][i]
                        })
            
            logger.debug(f"Found {len(search_results)} similar vectors")
            return search_results
            
        except Exception as e:
            logger.error(f"Failed to search similar vectors: {e}")
            raise
    
    async def get_vector(self, vector_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific vector by ID.
        
        Args:
            vector_id: Vector identifier
            
        Returns:
            Optional[Dict[str, Any]]: Vector data or None if not found
        """
        try:
            results = self.collection.get(
                ids=[vector_id],
                include=["documents", "metadatas"]
            )
            
            if results['ids'] and results['ids'][0]:
                return {
                    'id': vector_id,
                    'text': results['documents'][0],
                    'metadata': results['metadatas'][0]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get vector {vector_id}: {e}")
            return None
    
    async def delete_vector(self, vector_id: str) -> bool:
        """
        Delete a vector by ID.
        
        Args:
            vector_id: Vector identifier
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            self.collection.delete(ids=[vector_id])
            logger.debug(f"Deleted vector {vector_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete vector {vector_id}: {e}")
            return False
    
    async def delete_vectors_by_filter(self, filters: Dict[str, Any]) -> int:
        """
        Delete vectors matching filters.
        
        Args:
            filters: Metadata filters
            
        Returns:
            int: Number of vectors deleted
        """
        try:
            # Prepare where clause
            where_clause = {}
            for key, value in filters.items():
                if isinstance(value, list):
                    where_clause[key] = {"$in": value}
                else:
                    where_clause[key] = {"$eq": value}
            
            # Get matching vectors first to count them
            results = self.collection.get(
                where=where_clause,
                include=["documents"]
            )
            
            count = len(results['ids']) if results['ids'] else 0
            
            if count > 0:
                # Delete matching vectors
                self.collection.delete(where=where_clause)
                logger.info(f"Deleted {count} vectors matching filters")
            
            return count
            
        except Exception as e:
            logger.error(f"Failed to delete vectors by filter: {e}")
            return 0
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get collection statistics.
        
        Returns:
            Dict[str, Any]: Collection statistics
        """
        try:
            # Get collection count
            count_result = self.collection.count()
            
            return {
                "total_vectors": count_result,
                "collection_name": self.collection_name,
                "status": "healthy"
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {
                "total_vectors": 0,
                "collection_name": self.collection_name,
                "status": "error",
                "error": str(e)
            }
    
    async def reset_collection(self) -> bool:
        """
        Reset (clear) the collection.
        
        Returns:
            bool: True if reset successfully
        """
        try:
            # Delete the collection
            self.client.delete_collection(name=self.collection_name)
            
            # Recreate the collection
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "ACP Knowledge Base"}
            )
            
            logger.info(f"Reset collection: {self.collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset collection: {e}")
            return False

