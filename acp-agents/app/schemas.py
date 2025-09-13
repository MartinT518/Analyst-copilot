"""Pydantic schemas for the ACP Agents service."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from acp_shared_models.workflows import WorkflowStatus
from pydantic import BaseModel, Field, validator


class RequestType(str, Enum):
    """Request type enumeration."""

    BUSINESS_ANALYSIS = "business_analysis"
    REQUIREMENTS_GATHERING = "requirements_gathering"
    DEVELOPER_TASK_GENERATION = "developer_task_generation"
    SYSTEM_ANALYSIS = "system_analysis"


class WorkflowRequest(BaseModel):
    """Request to start a new workflow."""

    request_type: RequestType = Field(..., description="Type of workflow to start")
    initial_requirements: str = Field(..., description="Initial requirements or description")
    context: Optional[dict[str, Any]] = Field(None, description="Additional context information")
    priority: str = Field("medium", description="Workflow priority (low, medium, high)")
    client_id: Optional[str] = Field(None, description="Client identifier")

    @validator("initial_requirements")
    def validate_requirements(cls, v):
        if len(v.strip()) < 10:
            raise ValueError("Initial requirements must be at least 10 characters long")
        return v.strip()


class ClarifyingQuestion(BaseModel):
    """A single clarifying question."""

    question_id: str = Field(..., description="Unique question identifier")
    question: str = Field(..., description="The clarifying question text")
    question_type: str = Field(
        "open", description="Type of question (open, multiple_choice, yes_no)"
    )
    options: Optional[list[str]] = Field(None, description="Options for multiple choice questions")
    required: bool = Field(True, description="Whether this question is required")
    context: Optional[str] = Field(None, description="Additional context for the question")


class ClarifyingQuestions(BaseModel):
    """Collection of clarifying questions."""

    questions: list[ClarifyingQuestion] = Field(..., description="List of clarifying questions")
    instructions: str = Field(..., description="Instructions for answering questions")
    estimated_time: Optional[int] = Field(None, description="Estimated time to answer in minutes")


class ClientAnswer(BaseModel):
    """A single client answer."""

    question_id: str = Field(..., description="Question identifier")
    answer: str = Field(..., description="Client's answer")
    confidence: Optional[float] = Field(None, description="Client's confidence in the answer (0-1)")


class ClientAnswers(BaseModel):
    """Collection of client answers."""

    answers: list[ClientAnswer] = Field(..., description="List of client answers")
    additional_context: Optional[str] = Field(
        None, description="Additional context provided by client"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When answers were submitted"
    )


class ASISDocument(BaseModel):
    """AS-IS (current state) document."""

    title: str = Field(..., description="Document title")
    executive_summary: str = Field(..., description="Executive summary")
    current_state_description: str = Field(..., description="Description of current state")
    pain_points: list[str] = Field(..., description="List of identified pain points")
    stakeholders: list[str] = Field(..., description="List of stakeholders")
    processes: list[dict[str, Any]] = Field(..., description="Current processes")
    systems: list[dict[str, Any]] = Field(..., description="Current systems")
    data_flows: list[dict[str, Any]] = Field(..., description="Current data flows")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class TOBEDocument(BaseModel):
    """TO-BE (future state) document."""

    title: str = Field(..., description="Document title")
    executive_summary: str = Field(..., description="Executive summary")
    future_state_vision: str = Field(..., description="Vision for future state")
    benefits: list[str] = Field(..., description="Expected benefits")
    success_criteria: list[str] = Field(..., description="Success criteria")
    sections: list[dict[str, Any]] = Field(..., description="Document sections")
    implementation_approach: str = Field(..., description="High-level implementation approach")
    risks: list[str] = Field(..., description="Identified risks")
    assumptions: list[str] = Field(..., description="Key assumptions")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class UserStory(BaseModel):
    """User story for developer tasks."""

    story_id: str = Field(..., description="Unique story identifier")
    title: str = Field(..., description="Story title")
    description: str = Field(..., description="Story description")
    acceptance_criteria: list[str] = Field(..., description="Acceptance criteria")
    priority: str = Field("medium", description="Priority level")
    story_points: Optional[int] = Field(None, description="Estimated story points")
    epic: Optional[str] = Field(None, description="Epic this story belongs to")
    labels: list[str] = Field(default_factory=list, description="Story labels")


class TechnicalNote(BaseModel):
    """Technical note for implementation guidance."""

    note_id: str = Field(..., description="Unique note identifier")
    category: str = Field(
        ..., description="Note category (architecture, security, performance, etc.)"
    )
    description: str = Field(..., description="Technical note description")
    impact: str = Field("medium", description="Impact level (low, medium, high)")
    references: list[str] = Field(default_factory=list, description="Reference links or documents")


class DeveloperTask(BaseModel):
    """Developer task with user stories and technical notes."""

    task_id: str = Field(..., description="Unique task identifier")
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Task description")
    user_stories: list[UserStory] = Field(..., description="User stories for this task")
    technical_notes: list[TechnicalNote] = Field(..., description="Technical implementation notes")
    estimated_effort: str = Field(..., description="Estimated effort (e.g., '3 days', '2 weeks')")
    priority: str = Field("medium", description="Task priority")
    dependencies: list[str] = Field(default_factory=list, description="Task dependencies")
    labels: list[str] = Field(default_factory=list, description="Task labels")
    epic: Optional[str] = Field(None, description="Epic this task belongs to")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class VerificationFlag(BaseModel):
    """Verification flag for quality assurance."""

    flag_id: str = Field(..., description="Unique flag identifier")
    category: str = Field(..., description="Flag category (consistency, completeness, feasibility)")
    severity: str = Field("medium", description="Severity level (low, medium, high, critical)")
    description: str = Field(..., description="Flag description")
    recommendation: str = Field(..., description="Recommendation to address the flag")
    source: str = Field(
        ...,
        description="Source of the verification (knowledge_base, code_analysis, etc.)",
    )


class WorkflowResponse(BaseModel):
    """Response from workflow operations."""

    job_id: str = Field(..., description="Unique job identifier")
    status: WorkflowStatus = Field(..., description="Current workflow status")
    message: str = Field(..., description="Status message")
    clarifying_questions: Optional[ClarifyingQuestions] = Field(
        None, description="Clarifying questions if waiting for input"
    )
    estimated_completion: Optional[str] = Field(None, description="Estimated completion time")
    progress_percentage: Optional[int] = Field(None, description="Progress percentage (0-100)")
    current_step: Optional[str] = Field(None, description="Current workflow step")
    results: Optional[dict[str, Any]] = Field(None, description="Workflow results if completed")


class WorkflowStatus(BaseModel):
    """Detailed workflow status information."""

    job_id: str = Field(..., description="Unique job identifier")
    status: WorkflowStatus = Field(..., description="Current workflow status")
    created_at: datetime = Field(..., description="When workflow was created")
    updated_at: datetime = Field(..., description="When workflow was last updated")
    completed_at: Optional[datetime] = Field(None, description="When workflow was completed")
    progress_percentage: int = Field(0, description="Progress percentage (0-100)")
    current_step: Optional[str] = Field(None, description="Current workflow step")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    # Workflow state components
    initial_request: Optional[WorkflowRequest] = Field(None, description="Initial workflow request")
    retrieved_context: Optional[dict[str, Any]] = Field(
        None, description="Retrieved context from knowledge base"
    )
    clarifying_questions: Optional[ClarifyingQuestions] = Field(
        None, description="Generated clarifying questions"
    )
    client_answers: Optional[ClientAnswers] = Field(None, description="Client answers")
    asis_document: Optional[ASISDocument] = Field(None, description="AS-IS document")
    tobe_document: Optional[TOBEDocument] = Field(None, description="TO-BE document")
    developer_task: Optional[DeveloperTask] = Field(None, description="Generated developer task")
    verification_flags: list[VerificationFlag] = Field(
        default_factory=list, description="Verification flags"
    )
    history: list[dict[str, Any]] = Field(
        default_factory=list, description="Workflow execution history"
    )


class AgentMetrics(BaseModel):
    """Metrics for agent performance."""

    agent_type: str = Field(..., description="Type of agent")
    total_requests: int = Field(0, description="Total number of requests")
    successful_requests: int = Field(0, description="Number of successful requests")
    failed_requests: int = Field(0, description="Number of failed requests")
    average_duration: float = Field(0.0, description="Average request duration in seconds")
    success_rate: float = Field(0.0, description="Success rate percentage")
    last_updated: datetime = Field(
        default_factory=datetime.utcnow, description="When metrics were last updated"
    )


class SystemHealth(BaseModel):
    """System health information."""

    status: str = Field(..., description="Overall system status")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Health check timestamp"
    )
    services: dict[str, bool] = Field(..., description="Individual service health status")
    metrics: dict[str, Any] = Field(default_factory=dict, description="System metrics")
    errors: list[str] = Field(default_factory=list, description="Any errors or warnings")
