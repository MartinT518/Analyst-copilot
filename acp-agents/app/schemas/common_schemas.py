"""Common schemas used across agents."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


class WorkflowStatus(str, Enum):
    """Workflow execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class AgentType(str, Enum):
    """Types of agents in the system."""

    CLARIFIER = "clarifier"
    SYNTHESIZER = "synthesizer"
    TASKMASTER = "taskmaster"
    VERIFIER = "verifier"


class Priority(str, Enum):
    """Priority levels for tasks and workflows."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConfidenceLevel(str, Enum):
    """Confidence levels for agent outputs."""

    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class BaseAgentInput(BaseModel):
    """Base input schema for all agents."""

    request_id: str = Field(..., description="Unique identifier for the request")
    user_id: Optional[int] = Field(None, description="ID of the user making the request")
    context: Dict[str, Any] = Field(
        default_factory=dict, description="Additional context for the agent"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata about the request")


class BaseAgentOutput(BaseModel):
    """Base output schema for all agents."""

    agent_type: AgentType = Field(..., description="Type of agent that generated this output")
    request_id: str = Field(..., description="Request ID this output corresponds to")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score for the output")
    confidence_level: ConfidenceLevel = Field(..., description="Human-readable confidence level")
    reasoning: str = Field(..., description="Explanation of the agent's reasoning")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="When this output was generated"
    )

    @validator("confidence_level", pre=True, always=True)
    def set_confidence_level(cls, v, values):
        """Automatically set confidence level based on confidence score."""
        if "confidence" in values:
            confidence = values["confidence"]
            if confidence >= 0.9:
                return ConfidenceLevel.VERY_HIGH
            elif confidence >= 0.75:
                return ConfidenceLevel.HIGH
            elif confidence >= 0.5:
                return ConfidenceLevel.MEDIUM
            elif confidence >= 0.25:
                return ConfidenceLevel.LOW
            else:
                return ConfidenceLevel.VERY_LOW
        return v


class KnowledgeReference(BaseModel):
    """Reference to knowledge base content."""

    chunk_id: UUID = Field(..., description="ID of the knowledge chunk")
    source_type: str = Field(..., description="Type of source document")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Similarity score")
    excerpt: str = Field(..., description="Relevant excerpt from the knowledge")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ValidationResult(BaseModel):
    """Result of validation checks."""

    is_valid: bool = Field(..., description="Whether the validation passed")
    errors: List[str] = Field(default_factory=list, description="List of validation errors")
    warnings: List[str] = Field(default_factory=list, description="List of validation warnings")
    score: float = Field(..., ge=0.0, le=1.0, description="Validation score")


class WorkflowStep(BaseModel):
    """Individual step in a workflow."""

    step_id: str = Field(..., description="Unique identifier for the step")
    agent_type: AgentType = Field(..., description="Type of agent for this step")
    status: WorkflowStatus = Field(
        default=WorkflowStatus.PENDING, description="Status of this step"
    )
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Input data for the step")
    output_data: Optional[Dict[str, Any]] = Field(None, description="Output data from the step")
    started_at: Optional[datetime] = Field(None, description="When the step started")
    completed_at: Optional[datetime] = Field(None, description="When the step completed")
    error_message: Optional[str] = Field(None, description="Error message if step failed")
    duration_seconds: Optional[float] = Field(None, description="Duration of step execution")


class WorkflowContext(BaseModel):
    """Context shared across workflow steps."""

    workflow_id: str = Field(..., description="Unique workflow identifier")
    user_id: Optional[int] = Field(None, description="User who initiated the workflow")
    original_request: str = Field(..., description="Original user request")
    knowledge_references: List[KnowledgeReference] = Field(
        default_factory=list, description="Relevant knowledge"
    )
    shared_data: Dict[str, Any] = Field(
        default_factory=dict, description="Data shared between steps"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Workflow metadata")


class AgentMetrics(BaseModel):
    """Metrics for agent performance."""

    agent_type: AgentType = Field(..., description="Type of agent")
    total_requests: int = Field(default=0, description="Total number of requests processed")
    successful_requests: int = Field(default=0, description="Number of successful requests")
    failed_requests: int = Field(default=0, description="Number of failed requests")
    average_duration: float = Field(
        default=0.0, description="Average processing duration in seconds"
    )
    average_confidence: float = Field(default=0.0, description="Average confidence score")
    last_updated: datetime = Field(
        default_factory=datetime.utcnow, description="Last metrics update"
    )


class ErrorInfo(BaseModel):
    """Information about errors that occurred."""

    error_type: str = Field(..., description="Type of error")
    error_message: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")
    stack_trace: Optional[str] = Field(None, description="Stack trace")
    context: Dict[str, Any] = Field(default_factory=dict, description="Error context")
    occurred_at: datetime = Field(
        default_factory=datetime.utcnow, description="When the error occurred"
    )


class HealthStatus(BaseModel):
    """Health status of the agents service."""

    status: str = Field(..., description="Overall health status")
    version: str = Field(..., description="Service version")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")
    active_workflows: int = Field(..., description="Number of active workflows")
    total_agents: int = Field(..., description="Total number of agents")
    database_connected: bool = Field(..., description="Database connection status")
    redis_connected: bool = Field(..., description="Redis connection status")
    llm_available: bool = Field(..., description="LLM service availability")
    last_check: datetime = Field(
        default_factory=datetime.utcnow, description="Last health check time"
    )


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""

    page: int = Field(default=1, ge=1, description="Page number")
    size: int = Field(default=20, ge=1, le=100, description="Page size")

    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.size


class SortParams(BaseModel):
    """Sorting parameters for list endpoints."""

    sort_by: str = Field(default="created_at", description="Field to sort by")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort order")


class FilterParams(BaseModel):
    """Filtering parameters for list endpoints."""

    status: Optional[WorkflowStatus] = Field(None, description="Filter by status")
    agent_type: Optional[AgentType] = Field(None, description="Filter by agent type")
    user_id: Optional[int] = Field(None, description="Filter by user ID")
    date_from: Optional[datetime] = Field(None, description="Filter from date")
    date_to: Optional[datetime] = Field(None, description="Filter to date")


class ListResponse(BaseModel):
    """Generic list response with pagination."""

    items: List[Any] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size")
    pages: int = Field(..., description="Total number of pages")

    @validator("pages", pre=True, always=True)
    def calculate_pages(cls, v, values):
        """Calculate total pages based on total and size."""
        if "total" in values and "size" in values:
            total = values["total"]
            size = values["size"]
            return (total + size - 1) // size if total > 0 else 0
        return v
