"""Search API endpoints."""

from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
from app.services.search_service import SearchService
from app.services.auth_service import get_current_user
from app.utils.logging_config import get_logger, get_performance_logger

logger = get_logger(__name__)
performance_logger = get_performance_logger()

router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    """Search request model."""
    query: str = Field(..., description="Search query")
    limit: int = Field(10, ge=1, le=100, description="Maximum number of results")
    similarity_threshold: float = Field(0.7, ge=0.0, le=1.0, description="Minimum similarity score")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Search filters")


class ChunkResult(BaseModel):
    """Individual chunk result model."""
    id: str
    chunk_text: str
    chunk_index: int
    source_type: str
    metadata: Dict[str, Any]


class SearchResult(BaseModel):
    """Individual search result model."""
    chunk: ChunkResult
    similarity_score: float


class SearchResponse(BaseModel):
    """Search response model."""
    query: str
    results: List[SearchResult]
    total_results: int
    processing_time_ms: float
    filters_applied: Dict[str, Any]


@router.post("", response_model=SearchResponse)
async def search_knowledge(
    request: SearchRequest,
    db: Session = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """
    Search knowledge chunks using semantic similarity.
    
    Args:
        request: Search request with query and parameters
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        SearchResponse: Search results with similarity scores
    """
    start_time = datetime.utcnow()
    
    try:
        logger.info(
            "Search request received",
            query=request.query,
            limit=request.limit,
            threshold=request.similarity_threshold,
            user_id=current_user.get("user_id") if current_user else "anonymous"
        )
        
        # Initialize search service
        search_service = SearchService()
        
        # Apply user-based filtering for non-admin users
        filters = request.filters.copy()
        if current_user and not current_user.get("is_admin", False):
            # Add user filtering - users can only search their own data
            filters["user_id"] = current_user.get("user_id")
        
        # Perform search
        results = await search_service.search(
            query=request.query,
            limit=request.limit,
            similarity_threshold=request.similarity_threshold,
            filters=filters,
            db=db
        )
        
        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Format results
        search_results = []
        for result in results:
            chunk_data = result["chunk"]
            similarity_score = result["similarity_score"]
            
            chunk_result = ChunkResult(
                id=chunk_data["id"],
                chunk_text=chunk_data["chunk_text"],
                chunk_index=chunk_data["chunk_index"],
                source_type=chunk_data["source_type"],
                metadata=chunk_data["metadata"]
            )
            
            search_results.append(SearchResult(
                chunk=chunk_result,
                similarity_score=similarity_score
            ))
        
        # Log performance
        performance_logger.log_operation(
            operation="semantic_search",
            duration_ms=processing_time,
            success=True,
            details={
                "query_length": len(request.query),
                "results_count": len(search_results),
                "similarity_threshold": request.similarity_threshold
            }
        )
        
        logger.info(
            "Search completed",
            query=request.query,
            results_count=len(search_results),
            processing_time_ms=processing_time
        )
        
        return SearchResponse(
            query=request.query,
            results=search_results,
            total_results=len(search_results),
            processing_time_ms=processing_time,
            filters_applied=filters
        )
        
    except Exception as e:
        # Calculate processing time for error case
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Log performance failure
        performance_logger.log_operation(
            operation="semantic_search",
            duration_ms=processing_time,
            success=False,
            details={"error": str(e)}
        )
        
        logger.error("Search failed", query=request.query, error=str(e))
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/similar/{chunk_id}", response_model=SearchResponse)
async def find_similar_chunks(
    chunk_id: str,
    limit: int = 10,
    similarity_threshold: float = 0.7,
    db: Session = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """
    Find chunks similar to a specific chunk.
    
    Args:
        chunk_id: ID of the reference chunk
        limit: Maximum number of results
        similarity_threshold: Minimum similarity score
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        SearchResponse: Similar chunks with similarity scores
    """
    start_time = datetime.utcnow()
    
    try:
        logger.info(
            "Similar chunks request",
            chunk_id=chunk_id,
            limit=limit,
            threshold=similarity_threshold
        )
        
        # Initialize search service
        search_service = SearchService()
        
        # Apply user-based filtering for non-admin users
        filters = {}
        if current_user and not current_user.get("is_admin", False):
            filters["user_id"] = current_user.get("user_id")
        
        # Find similar chunks
        results = await search_service.find_similar(
            chunk_id=chunk_id,
            limit=limit,
            similarity_threshold=similarity_threshold,
            filters=filters,
            db=db
        )
        
        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Format results
        search_results = []
        for result in results:
            chunk_data = result["chunk"]
            similarity_score = result["similarity_score"]
            
            chunk_result = ChunkResult(
                id=chunk_data["id"],
                chunk_text=chunk_data["chunk_text"],
                chunk_index=chunk_data["chunk_index"],
                source_type=chunk_data["source_type"],
                metadata=chunk_data["metadata"]
            )
            
            search_results.append(SearchResult(
                chunk=chunk_result,
                similarity_score=similarity_score
            ))
        
        # Log performance
        performance_logger.log_operation(
            operation="similar_chunks_search",
            duration_ms=processing_time,
            success=True,
            details={
                "chunk_id": chunk_id,
                "results_count": len(search_results),
                "similarity_threshold": similarity_threshold
            }
        )
        
        logger.info(
            "Similar chunks search completed",
            chunk_id=chunk_id,
            results_count=len(search_results),
            processing_time_ms=processing_time
        )
        
        return SearchResponse(
            query=f"Similar to chunk {chunk_id}",
            results=search_results,
            total_results=len(search_results),
            processing_time_ms=processing_time,
            filters_applied=filters
        )
        
    except Exception as e:
        # Calculate processing time for error case
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Log performance failure
        performance_logger.log_operation(
            operation="similar_chunks_search",
            duration_ms=processing_time,
            success=False,
            details={"error": str(e)}
        )
        
        logger.error("Similar chunks search failed", chunk_id=chunk_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Similar chunks search failed: {str(e)}")


@router.get("/filters")
async def get_available_filters(
    db: Session = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """
    Get available filter options for search.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Available filter options
    """
    try:
        search_service = SearchService()
        
        # Apply user-based filtering for non-admin users
        user_filter = None
        if current_user and not current_user.get("is_admin", False):
            user_filter = current_user.get("user_id")
        
        filters = await search_service.get_available_filters(db=db, user_id=user_filter)
        
        logger.debug("Available filters retrieved", filters=filters)
        
        return filters
        
    except Exception as e:
        logger.error("Failed to get available filters", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get filters: {str(e)}")


@router.post("/export")
async def export_search_results(
    request: SearchRequest,
    format: str = "json",
    db: Session = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """
    Export search results in various formats.
    
    Args:
        request: Search request
        format: Export format (json, csv, txt)
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        File response with search results
    """
    try:
        if format not in ["json", "csv", "txt"]:
            raise HTTPException(status_code=400, detail="Unsupported export format")
        
        # Perform search (reuse search logic)
        search_service = SearchService()
        
        filters = request.filters.copy()
        if current_user and not current_user.get("is_admin", False):
            filters["user_id"] = current_user.get("user_id")
        
        results = await search_service.search(
            query=request.query,
            limit=request.limit,
            similarity_threshold=request.similarity_threshold,
            filters=filters,
            db=db
        )
        
        # Export results
        exported_data = await search_service.export_results(results, format)
        
        logger.info(
            "Search results exported",
            query=request.query,
            format=format,
            results_count=len(results)
        )
        
        # Return appropriate response based on format
        if format == "json":
            from fastapi.responses import JSONResponse
            return JSONResponse(content=exported_data)
        elif format == "csv":
            from fastapi.responses import Response
            return Response(
                content=exported_data,
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=search_results.csv"}
            )
        elif format == "txt":
            from fastapi.responses import Response
            return Response(
                content=exported_data,
                media_type="text/plain",
                headers={"Content-Disposition": "attachment; filename=search_results.txt"}
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Export failed", query=request.query, format=format, error=str(e))
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/stats")
async def get_search_stats(
    db: Session = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """
    Get search and knowledge base statistics.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dict[str, Any]: Search statistics
    """
    try:
        search_service = SearchService()
        
        # Apply user-based filtering for non-admin users
        user_filter = None
        if current_user and not current_user.get("is_admin", False):
            user_filter = current_user.get("user_id")
        
        stats = await search_service.get_stats(db=db, user_id=user_filter)
        
        logger.debug("Search stats retrieved", stats=stats)
        
        return stats
        
    except Exception as e:
        logger.error("Failed to get search stats", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get search stats: {str(e)}")

