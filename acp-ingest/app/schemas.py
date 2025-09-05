"""Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field, validator
from enum import Enum


class SensitivityLevel(str, Enum):
    """Sensitivity levels for data classification."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class SourceType(str, Enum):
    """Supported source types for ingestion."""
    JIRA_CSV = "jira_csv"
    CONFLUENCE_HTML = "confluence_html"
    CONFLUENCE_XML = "confluence_xml"
    MARKDOWN = "markdown"
    PDF = "pdf"
    PASTE = "paste"
    ZIP = "zip"


class JobStatus(str, Enum):
    """Job processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class UserRole(str, Enum):
    """User roles for RBAC."""
    ANALYST = "analyst"
    REVIEWER = "reviewer"
    ADMIN = "admin"


# Request schemas
class IngestUploadRequest(BaseModel):
    """Schema for file upload requests."""
    origin: str = Field(..., description="Customer or source identifier")
    sensitivity: SensitivityLevel = Field(..., description="Data sensitivity level")
    source_type: Optional[SourceType] = Field(None, description="Source type (auto-detected if not provided)")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class IngestPasteRequest(BaseModel):
    """Schema for paste text requests."""
    text: str = Field(..., min_length=1, max_length=100000, description="Text content to ingest")
    origin: str = Field(..., description="Customer or source identifier")
    ticket_id: Optional[str] = Field(None, description="Ticket or document ID")
    sensitivity: SensitivityLevel = Field(..., description="Data sensitivity level")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class ChunkSearchRequest(BaseModel):
    """Schema for semantic search requests."""
    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum number of results")
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum similarity score")
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadata filters")


# Response schemas
class ChunkResponse(BaseModel):
    """Schema for knowledge chunk responses."""
    id: UUID
    source_type: str
    source_location: Optional[str]
    chunk_text: str
    metadata: Dict[str, Any]
    embedding_model: Optional[str]
    indexed_at: datetime
    sensitive: bool
    redacted: bool

    class Config:
        from_attributes = True


class JobResponse(BaseModel):
    """Schema for job status responses."""
    id: UUID
    status: JobStatus
    source_type: str
    origin: str
    sensitivity: str
    uploader: str
    chunks_created: int
    error_message: Optional[str]
    metadata: Dict[str, Any]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class SearchResult(BaseModel):
    """Schema for search result items."""
    chunk: ChunkResponse
    similarity_score: float
    rank: int


class SearchResponse(BaseModel):
    """Schema for search responses."""
    query: str
    results: List[SearchResult]
    total_results: int
    processing_time_ms: int


class IngestResponse(BaseModel):
    """Schema for ingestion responses."""
    job_id: UUID
    status: JobStatus
    message: str
    estimated_processing_time: Optional[int] = Field(None, description="Estimated processing time in seconds")


class HealthResponse(BaseModel):
    """Schema for health check responses."""
    status: str
    version: str
    timestamp: datetime
    services: Dict[str, str]


class ErrorResponse(BaseModel):
    """Schema for error responses."""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime


# User management schemas
class UserCreate(BaseModel):
    """Schema for user creation."""
    username: str = Field(..., min_length=3, max_length=100)
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(..., min_length=8)
    role: UserRole = Field(default=UserRole.ANALYST)


class UserResponse(BaseModel):
    """Schema for user responses."""
    id: UUID
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Schema for authentication token responses."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# API Key schemas
class APIKeyCreate(BaseModel):
    """Schema for API key creation."""
    name: str = Field(..., min_length=1, max_length=100)
    permissions: List[str] = Field(default_factory=list)
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)


class APIKeyResponse(BaseModel):
    """Schema for API key responses."""
    id: UUID
    name: str
    key: Optional[str] = Field(None, description="Only returned on creation")
    permissions: List[str]
    is_active: bool
    expires_at: Optional[datetime]
    created_at: datetime
    last_used: Optional[datetime]

    class Config:
        from_attributes = True


# Statistics and monitoring schemas
class ProcessingStats(BaseModel):
    """Schema for processing statistics."""
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    pending_jobs: int
    total_chunks: int
    average_processing_time: float
    last_24h_jobs: int


class SystemStatus(BaseModel):
    """Schema for system status."""
    database_connected: bool
    vector_db_connected: bool
    embedding_service_available: bool
    llm_service_available: bool
    redis_connected: bool
    disk_usage_percent: float
    memory_usage_percent: float

