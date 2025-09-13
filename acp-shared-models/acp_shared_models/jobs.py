"""Job related models."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import Field

from .common import BaseModel, PaginatedResponse


class JobStatus(str, Enum):
    """Job status enumeration."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IngestJobResponse(BaseModel):
    """Ingest job response model."""

    id: str = Field(..., description="Job ID")
    status: str = Field(..., description="Job status")
    origin: str = Field(..., description="Job origin")
    source_type: str = Field(..., description="Source type")
    sensitivity: str = Field(..., description="Sensitivity level")
    chunks_created: int = Field(0, description="Number of chunks created")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    metadata: Optional[dict[str, Any]] = Field(None, description="Job metadata")


class JobListResponse(PaginatedResponse[IngestJobResponse]):
    """Job list response model."""

    jobs: list[IngestJobResponse] = Field(..., alias="items", description="List of jobs")

    class Config:
        """Pydantic configuration."""

        allow_population_by_field_name = True
