"""Schemas for workflow management and orchestration."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

from .agent_schemas import ClarifierOutput, SynthesizerOutput, TaskmasterOutput, VerifierOutput
from .common_schemas import AgentType, Priority, WorkflowContext, WorkflowStatus, WorkflowStep


class WorkflowType(str, Enum):
    """Types of workflows supported."""

    FULL_ANALYSIS = "full_analysis"  # Complete workflow with all agents
    CLARIFICATION_ONLY = "clarification_only"  # Only clarifier
    SYNTHESIS_ONLY = "synthesis_only"  # Only synthesizer
    TASK_GENERATION = "task_generation"  # Clarifier + Synthesizer + Taskmaster
    VERIFICATION_ONLY = "verification_only"  # Only verifier
    CUSTOM = "custom"  # Custom workflow definition


class WorkflowTrigger(str, Enum):
    """What triggered the workflow."""

    USER_REQUEST = "user_request"
    API_CALL = "api_call"
    SCHEDULED = "scheduled"
    WEBHOOK = "webhook"
    RETRY = "retry"


class WorkflowRequest(BaseModel):
    """Request to start a new workflow."""

    workflow_type: WorkflowType = Field(..., description="Type of workflow to execute")
    user_request: str = Field(..., description="Original user request")
    user_id: Optional[int] = Field(None, description="ID of the requesting user")
    priority: Priority = Field(default=Priority.MEDIUM, description="Workflow priority")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Request metadata")

    # Optional inputs for specific workflow types
    clarified_requirements: Optional[Dict[str, Any]] = Field(
        None, description="Pre-clarified requirements"
    )
    knowledge_filter: Optional[Dict[str, str]] = Field(None, description="Knowledge base filters")
    custom_steps: Optional[List[str]] = Field(None, description="Custom workflow steps")

    # Configuration overrides
    config_overrides: Dict[str, Any] = Field(
        default_factory=dict, description="Configuration overrides"
    )


class WorkflowResponse(BaseModel):
    """Response when starting a workflow."""

    workflow_id: str = Field(..., description="Unique workflow identifier")
    status: WorkflowStatus = Field(..., description="Initial workflow status")
    estimated_duration_minutes: Optional[int] = Field(None, description="Estimated completion time")
    steps_planned: List[str] = Field(..., description="Planned workflow steps")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="When workflow was created"
    )


class WorkflowExecution(BaseModel):
    """Complete workflow execution state."""

    workflow_id: str = Field(..., description="Unique workflow identifier")
    workflow_type: WorkflowType = Field(..., description="Type of workflow")
    status: WorkflowStatus = Field(..., description="Current workflow status")
    priority: Priority = Field(..., description="Workflow priority")

    # Timing information
    created_at: datetime = Field(..., description="When workflow was created")
    started_at: Optional[datetime] = Field(None, description="When workflow started")
    completed_at: Optional[datetime] = Field(None, description="When workflow completed")
    duration_seconds: Optional[float] = Field(None, description="Total execution duration")

    # User and context
    user_id: Optional[int] = Field(None, description="User who initiated the workflow")
    original_request: str = Field(..., description="Original user request")
    context: WorkflowContext = Field(..., description="Workflow context")

    # Execution details
    steps: List[WorkflowStep] = Field(..., description="Workflow steps")
    current_step: Optional[str] = Field(None, description="Currently executing step")

    # Results
    results: Dict[str, Any] = Field(default_factory=dict, description="Workflow results")
    error_message: Optional[str] = Field(None, description="Error message if failed")

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Workflow metadata")

    @validator("duration_seconds", pre=True, always=True)
    def calculate_duration(cls, v, values):
        """Calculate duration if not provided."""
        if v is None and "started_at" in values and "completed_at" in values:
            started = values["started_at"]
            completed = values["completed_at"]
            if started and completed:
                return (completed - started).total_seconds()
        return v


class WorkflowResults(BaseModel):
    """Complete results from a workflow execution."""

    workflow_id: str = Field(..., description="Workflow identifier")
    workflow_type: WorkflowType = Field(..., description="Type of workflow")
    status: WorkflowStatus = Field(..., description="Final workflow status")

    # Agent outputs
    clarifier_output: Optional[ClarifierOutput] = Field(None, description="Clarifier agent results")
    synthesizer_output: Optional[SynthesizerOutput] = Field(
        None, description="Synthesizer agent results"
    )
    taskmaster_output: Optional[TaskmasterOutput] = Field(
        None, description="Taskmaster agent results"
    )
    verifier_output: Optional[VerifierOutput] = Field(None, description="Verifier agent results")

    # Summary information
    summary: str = Field(..., description="Summary of workflow results")
    recommendations: List[str] = Field(default_factory=list, description="Key recommendations")
    next_steps: List[str] = Field(default_factory=list, description="Suggested next steps")

    # Quality metrics
    overall_confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score")
    quality_score: float = Field(..., ge=0.0, le=1.0, description="Quality score")

    # Execution metadata
    execution_time_seconds: float = Field(..., description="Total execution time")
    steps_completed: int = Field(..., description="Number of steps completed")
    knowledge_references_used: int = Field(..., description="Number of knowledge references used")

    # Export information
    export_formats: List[str] = Field(default_factory=list, description="Available export formats")

    # Timestamps
    completed_at: datetime = Field(
        default_factory=datetime.utcnow, description="When results were finalized"
    )


class WorkflowUpdate(BaseModel):
    """Update to workflow execution."""

    workflow_id: str = Field(..., description="Workflow identifier")
    step_id: Optional[str] = Field(None, description="Step being updated")
    status: Optional[WorkflowStatus] = Field(None, description="New status")
    progress_percentage: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="Progress percentage"
    )
    message: Optional[str] = Field(None, description="Update message")
    data: Dict[str, Any] = Field(default_factory=dict, description="Additional update data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Update timestamp")


class WorkflowMetrics(BaseModel):
    """Metrics for workflow performance."""

    total_workflows: int = Field(default=0, description="Total workflows executed")
    successful_workflows: int = Field(default=0, description="Successfully completed workflows")
    failed_workflows: int = Field(default=0, description="Failed workflows")
    average_duration_seconds: float = Field(default=0.0, description="Average execution duration")

    # By workflow type
    metrics_by_type: Dict[WorkflowType, Dict[str, Any]] = Field(
        default_factory=dict, description="Metrics broken down by workflow type"
    )

    # By time period
    daily_metrics: Dict[str, int] = Field(default_factory=dict, description="Daily workflow counts")
    hourly_metrics: Dict[str, int] = Field(
        default_factory=dict, description="Hourly workflow counts"
    )

    # Performance metrics
    p50_duration_seconds: float = Field(default=0.0, description="50th percentile duration")
    p95_duration_seconds: float = Field(default=0.0, description="95th percentile duration")
    p99_duration_seconds: float = Field(default=0.0, description="99th percentile duration")

    last_updated: datetime = Field(
        default_factory=datetime.utcnow, description="Last metrics update"
    )


class WorkflowTemplate(BaseModel):
    """Template for creating workflows."""

    template_id: str = Field(..., description="Unique template identifier")
    name: str = Field(..., description="Template name")
    description: str = Field(..., description="Template description")
    workflow_type: WorkflowType = Field(..., description="Type of workflow")

    # Template configuration
    default_steps: List[str] = Field(..., description="Default workflow steps")
    required_inputs: List[str] = Field(..., description="Required input fields")
    optional_inputs: List[str] = Field(default_factory=list, description="Optional input fields")

    # Default settings
    default_priority: Priority = Field(default=Priority.MEDIUM, description="Default priority")
    estimated_duration_minutes: int = Field(..., description="Estimated duration")

    # Configuration
    config: Dict[str, Any] = Field(default_factory=dict, description="Template configuration")

    # Metadata
    created_by: Optional[str] = Field(None, description="Template creator")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    version: str = Field(default="1.0", description="Template version")
    is_active: bool = Field(default=True, description="Whether template is active")


class WorkflowSchedule(BaseModel):
    """Schedule for recurring workflows."""

    schedule_id: str = Field(..., description="Unique schedule identifier")
    name: str = Field(..., description="Schedule name")
    workflow_template_id: str = Field(..., description="Template to use")

    # Schedule configuration
    cron_expression: str = Field(..., description="Cron expression for scheduling")
    timezone: str = Field(default="UTC", description="Timezone for schedule")

    # Input configuration
    input_template: Dict[str, Any] = Field(default_factory=dict, description="Input template")
    context_template: Dict[str, Any] = Field(default_factory=dict, description="Context template")

    # Status
    is_active: bool = Field(default=True, description="Whether schedule is active")
    next_run: Optional[datetime] = Field(None, description="Next scheduled run")
    last_run: Optional[datetime] = Field(None, description="Last run timestamp")

    # Metadata
    created_by: Optional[str] = Field(None, description="Schedule creator")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")


class WorkflowAudit(BaseModel):
    """Audit record for workflow execution."""

    audit_id: str = Field(..., description="Unique audit identifier")
    workflow_id: str = Field(..., description="Workflow identifier")
    event_type: str = Field(..., description="Type of audit event")
    event_description: str = Field(..., description="Description of the event")

    # Context
    user_id: Optional[int] = Field(None, description="User associated with event")
    agent_type: Optional[AgentType] = Field(None, description="Agent associated with event")
    step_id: Optional[str] = Field(None, description="Step associated with event")

    # Data
    before_state: Optional[Dict[str, Any]] = Field(None, description="State before event")
    after_state: Optional[Dict[str, Any]] = Field(None, description="State after event")
    event_data: Dict[str, Any] = Field(default_factory=dict, description="Additional event data")

    # Provenance
    source_ip: Optional[str] = Field(None, description="Source IP address")
    user_agent: Optional[str] = Field(None, description="User agent")
    session_id: Optional[str] = Field(None, description="Session identifier")

    # Timing
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")

    # Integrity
    hash_chain: Optional[str] = Field(None, description="Hash chain for integrity")
    signature: Optional[str] = Field(None, description="Digital signature")
