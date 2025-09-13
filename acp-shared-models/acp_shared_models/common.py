"""Common shared models."""

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field

T = TypeVar("T")


class BaseModel(PydanticBaseModel):
    """Base model with common configuration."""

    class Config:
        """Pydantic configuration."""

        use_enum_values = True
        validate_assignment = True
        extra = "forbid"
        json_encoders = {datetime: lambda v: v.isoformat()}


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Check timestamp")
    version: str = Field("1.0.0", description="Service version")
    services: Optional[dict[str, Any]] = Field(None, description="Service dependencies status")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""

    items: list[T] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    skip: int = Field(0, description="Number of items skipped")
    limit: int = Field(10, description="Maximum number of items per page")
    has_more: bool = Field(False, description="Whether there are more items available")
