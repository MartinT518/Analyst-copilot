"""Schemas for individual agent inputs and outputs."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .common_schemas import BaseAgentInput, BaseAgentOutput, KnowledgeReference, ValidationResult


# Clarifier Agent Schemas
class ClarificationQuestion(BaseModel):
    """A single clarification question."""

    question_id: str = Field(..., description="Unique identifier for the question")
    question: str = Field(..., description="The clarification question")
    question_type: str = Field(
        ..., description="Type of question (requirement, constraint, scope, etc.)"
    )
    importance: str = Field(..., description="Importance level (critical, high, medium, low)")
    suggested_answers: List[str] = Field(
        default_factory=list, description="Suggested answer options"
    )
    context: str = Field(..., description="Context explaining why this question is needed")


class ClarifierInput(BaseAgentInput):
    """Input schema for the Clarifier agent."""

    user_request: str = Field(..., description="Original user request to clarify")
    domain_context: Optional[str] = Field(None, description="Domain-specific context")
    existing_requirements: List[str] = Field(
        default_factory=list, description="Already known requirements"
    )


class ClarifierOutput(BaseAgentOutput):
    """Output schema for the Clarifier agent."""

    questions: List[ClarificationQuestion] = Field(
        ..., description="List of clarification questions"
    )
    analysis_summary: str = Field(..., description="Summary of the request analysis")
    identified_gaps: List[str] = Field(..., description="Identified gaps in the request")
    assumptions: List[str] = Field(..., description="Assumptions made during analysis")


# Synthesizer Agent Schemas
class DocumentSection(BaseModel):
    """A section in a document."""

    section_id: str = Field(..., description="Unique identifier for the section")
    title: str = Field(..., description="Section title")
    content: str = Field(..., description="Section content")
    section_type: str = Field(..., description="Type of section (overview, requirements, etc.)")
    order: int = Field(..., description="Order of the section in the document")
    subsections: List["DocumentSection"] = Field(
        default_factory=list, description="Nested subsections"
    )


class AsIsDocument(BaseModel):
    """AS-IS state documentation."""

    title: str = Field(..., description="Document title")
    executive_summary: str = Field(..., description="Executive summary")
    sections: List[DocumentSection] = Field(..., description="Document sections")
    current_state_analysis: str = Field(..., description="Analysis of current state")
    pain_points: List[str] = Field(..., description="Identified pain points")
    constraints: List[str] = Field(..., description="Current constraints")


class ToBeDocument(BaseModel):
    """TO-BE state documentation."""

    title: str = Field(..., description="Document title")
    executive_summary: str = Field(..., description="Executive summary")
    sections: List[DocumentSection] = Field(..., description="Document sections")
    future_state_vision: str = Field(..., description="Vision for future state")
    benefits: List[str] = Field(..., description="Expected benefits")
    success_criteria: List[str] = Field(..., description="Success criteria")


class GapAnalysis(BaseModel):
    """Gap analysis between AS-IS and TO-BE states."""

    gap_id: str = Field(..., description="Unique identifier for the gap")
    gap_description: str = Field(..., description="Description of the gap")
    impact: str = Field(..., description="Impact level (high, medium, low)")
    effort: str = Field(..., description="Effort required to close the gap")
    priority: str = Field(..., description="Priority level")
    recommendations: List[str] = Field(..., description="Recommendations to address the gap")


class SynthesizerInput(BaseAgentInput):
    """Input schema for the Synthesizer agent."""

    clarified_requirements: Dict[str, Any] = Field(
        ..., description="Clarified requirements from user"
    )
    knowledge_context: List[KnowledgeReference] = Field(
        ..., description="Relevant knowledge base content"
    )
    scope_boundaries: Optional[str] = Field(None, description="Defined scope boundaries")


class SynthesizerOutput(BaseAgentOutput):
    """Output schema for the Synthesizer agent."""

    as_is_document: AsIsDocument = Field(..., description="AS-IS state documentation")
    to_be_document: ToBeDocument = Field(..., description="TO-BE state documentation")
    gap_analysis: List[GapAnalysis] = Field(..., description="Gap analysis between states")
    implementation_approach: str = Field(..., description="Recommended implementation approach")
    risks_and_mitigation: List[str] = Field(
        ..., description="Identified risks and mitigation strategies"
    )


# Taskmaster Agent Schemas
class AcceptanceCriteria(BaseModel):
    """Acceptance criteria for a task."""

    criteria_id: str = Field(..., description="Unique identifier for the criteria")
    description: str = Field(..., description="Criteria description")
    test_scenario: str = Field(..., description="How to test this criteria")
    priority: str = Field(..., description="Priority of this criteria")


class TechnicalNote(BaseModel):
    """Technical implementation note."""

    note_id: str = Field(..., description="Unique identifier for the note")
    category: str = Field(..., description="Category (architecture, security, performance, etc.)")
    description: str = Field(..., description="Technical note description")
    impact: str = Field(..., description="Impact on implementation")
    references: List[str] = Field(default_factory=list, description="References to documentation")


class DeveloperTask(BaseModel):
    """A developer task/user story."""

    task_id: str = Field(..., description="Unique identifier for the task")
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Detailed task description")
    user_story: str = Field(..., description="User story format description")
    acceptance_criteria: List[AcceptanceCriteria] = Field(..., description="Acceptance criteria")
    technical_notes: List[TechnicalNote] = Field(..., description="Technical implementation notes")
    estimated_effort: str = Field(..., description="Estimated effort (story points or hours)")
    priority: str = Field(..., description="Task priority")
    dependencies: List[str] = Field(default_factory=list, description="Dependencies on other tasks")
    labels: List[str] = Field(default_factory=list, description="Labels for categorization")
    epic: Optional[str] = Field(None, description="Epic this task belongs to")


class TaskmasterInput(BaseAgentInput):
    """Input schema for the Taskmaster agent."""

    to_be_document: ToBeDocument = Field(..., description="TO-BE state documentation")
    gap_analysis: List[GapAnalysis] = Field(..., description="Gap analysis")
    implementation_approach: str = Field(..., description="Implementation approach")
    project_constraints: Dict[str, Any] = Field(
        default_factory=dict, description="Project constraints"
    )


class TaskmasterOutput(BaseAgentOutput):
    """Output schema for the Taskmaster agent."""

    tasks: List[DeveloperTask] = Field(..., description="Generated developer tasks")
    task_breakdown_summary: str = Field(..., description="Summary of task breakdown approach")
    implementation_phases: List[str] = Field(..., description="Recommended implementation phases")
    resource_requirements: Dict[str, Any] = Field(..., description="Required resources")
    timeline_estimate: str = Field(..., description="Estimated timeline")


# Verifier Agent Schemas
class VerificationCheck(BaseModel):
    """Individual verification check."""

    check_id: str = Field(..., description="Unique identifier for the check")
    check_type: str = Field(..., description="Type of verification check")
    description: str = Field(..., description="What is being verified")
    result: bool = Field(..., description="Whether the check passed")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the verification")
    details: str = Field(..., description="Detailed explanation of the check")
    references: List[KnowledgeReference] = Field(
        default_factory=list, description="Supporting references"
    )


class ConsistencyCheck(BaseModel):
    """Consistency check between different outputs."""

    source_a: str = Field(..., description="First source being compared")
    source_b: str = Field(..., description="Second source being compared")
    consistency_score: float = Field(..., ge=0.0, le=1.0, description="Consistency score")
    inconsistencies: List[str] = Field(default_factory=list, description="Found inconsistencies")
    recommendations: List[str] = Field(
        default_factory=list, description="Recommendations to resolve"
    )


class VerifierInput(BaseAgentInput):
    """Input schema for the Verifier agent."""

    clarifier_output: Optional[ClarifierOutput] = Field(None, description="Clarifier agent output")
    synthesizer_output: Optional[SynthesizerOutput] = Field(
        None, description="Synthesizer agent output"
    )
    taskmaster_output: Optional[TaskmasterOutput] = Field(
        None, description="Taskmaster agent output"
    )
    knowledge_base_context: List[KnowledgeReference] = Field(
        ..., description="Knowledge base context"
    )
    code_context: List[Dict[str, Any]] = Field(default_factory=list, description="Code context")
    schema_context: List[Dict[str, Any]] = Field(
        default_factory=list, description="Database schema context"
    )


class VerifierOutput(BaseAgentOutput):
    """Output schema for the Verifier agent."""

    verification_checks: List[VerificationCheck] = Field(
        ..., description="Individual verification checks"
    )
    consistency_checks: List[ConsistencyCheck] = Field(..., description="Consistency checks")
    overall_validation: ValidationResult = Field(..., description="Overall validation result")
    recommendations: List[str] = Field(..., description="Recommendations for improvement")
    flagged_issues: List[str] = Field(..., description="Issues that need attention")
    approval_status: str = Field(
        ..., description="Approval status (approved, needs_review, rejected)"
    )


# Enable forward references
DocumentSection.model_rebuild()
