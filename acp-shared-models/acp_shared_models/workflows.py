"""Workflow related models."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import Field

from .common import BaseModel


class WorkflowStatus(str, Enum):
    """Workflow status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ClientAnswers(BaseModel):
    """Client answers model."""

    answers: dict[str, Any] = Field(..., description="Client answers")


class WorkflowRequest(BaseModel):
    """Workflow request model."""

    workflow_type: str = Field(..., description="Type of workflow")
    input_data: dict[str, Any] = Field(..., description="Input data for workflow")
    client_answers: Optional[ClientAnswers] = Field(None, description="Client answers")


class WorkflowResponse(BaseModel):
    """Workflow response model."""

    workflow_id: str = Field(..., description="Workflow ID")
    status: str = Field(..., description="Workflow status")
    result: Optional[dict[str, Any]] = Field(None, description="Workflow result")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
