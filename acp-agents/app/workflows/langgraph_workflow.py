"""LangGraph-based workflow orchestration for multi-agent execution."""

import asyncio
from typing import Dict, Any, List, Optional, TypedDict
from datetime import datetime
import structlog
from langgraph import StateGraph, END
from langgraph.graph import Graph

from ..config import get_settings
from ..schemas.common_schemas import WorkflowStatus, AgentType
from ..schemas.workflow_schemas import WorkflowType, WorkflowExecution, WorkflowStep
from ..schemas.agent_schemas import ClarifierOutput, SynthesizerOutput, TaskmasterOutput, VerifierOutput
from ..agents import ClarifierAgent, SynthesizerAgent, TaskmasterAgent, VerifierAgent
from ..services import LLMService, KnowledgeService, AuditService

logger = structlog.get_logger(__name__)


class WorkflowState(TypedDict):
    """State object for LangGraph workflow."""
    workflow_id: str
    workflow_type: WorkflowType
    user_request: str
    user_id: Optional[int]
    
    # Agent outputs
    clarifier_output: Optional[ClarifierOutput]
    synthesizer_output: Optional[SynthesizerOutput]
    taskmaster_output: Optional[TaskmasterOutput]
    verifier_output: Optional[VerifierOutput]
    
    # Workflow metadata
    current_step: str
    steps_completed: List[str]
    errors: List[str]
    metadata: Dict[str, Any]


class LangGraphWorkflow:
    """LangGraph-based workflow orchestration system."""
    
    def __init__(
        self,
        llm_service: LLMService,
        knowledge_service: KnowledgeService,
        audit_service: AuditService
    ):
        """Initialize the LangGraph workflow system.
        
        Args:
            llm_service: LLM service instance
            knowledge_service: Knowledge service instance
            audit_service: Audit service instance
        """
        self.settings = get_settings()
        self.llm_service = llm_service
        self.knowledge_service = knowledge_service
        self.audit_service = audit_service
        self.logger = logger.bind(component="langgraph_workflow")
        
        # Initialize agents
        self.clarifier = ClarifierAgent(llm_service, knowledge_service, audit_service)
        self.synthesizer = SynthesizerAgent(llm_service, knowledge_service, audit_service)
        self.taskmaster = TaskmasterAgent(llm_service, knowledge_service, audit_service)
        self.verifier = VerifierAgent(llm_service, knowledge_service, audit_service)
        
        # Build workflow graphs
        self.workflows = {
            WorkflowType.FULL_ANALYSIS: self._build_full_analysis_workflow(),
            WorkflowType.CLARIFICATION_ONLY: self._build_clarification_workflow(),
            WorkflowType.SYNTHESIS_ONLY: self._build_synthesis_workflow(),
            WorkflowType.TASK_GENERATION: self._build_task_generation_workflow(),
            WorkflowType.VERIFICATION_ONLY: self._build_verification_workflow()
        }
    
    def _build_full_analysis_workflow(self) -> Graph:
        """Build the full analysis workflow with all agents.
        
        Returns:
            LangGraph workflow
        """
        workflow = StateGraph(WorkflowState)
        
        # Add nodes
        workflow.add_node("clarifier", self._clarifier_node)
        workflow.add_node("synthesizer", self._synthesizer_node)
        workflow.add_node("taskmaster", self._taskmaster_node)
        workflow.add_node("verifier", self._verifier_node)
        
        # Define edges
        workflow.set_entry_point("clarifier")
        workflow.add_edge("clarifier", "synthesizer")
        workflow.add_edge("synthesizer", "taskmaster")
        workflow.add_edge("taskmaster", "verifier")
        workflow.add_edge("verifier", END)
        
        return workflow.compile()
    
    def _build_clarification_workflow(self) -> Graph:
        """Build clarification-only workflow.
        
        Returns:
            LangGraph workflow
        """
        workflow = StateGraph(WorkflowState)
        
        workflow.add_node("clarifier", self._clarifier_node)
        workflow.set_entry_point("clarifier")
        workflow.add_edge("clarifier", END)
        
        return workflow.compile()
    
    def _build_synthesis_workflow(self) -> Graph:
        """Build synthesis-only workflow.
        
        Returns:
            LangGraph workflow
        """
        workflow = StateGraph(WorkflowState)
        
        workflow.add_node("synthesizer", self._synthesizer_node)
        workflow.set_entry_point("synthesizer")
        workflow.add_edge("synthesizer", END)
        
        return workflow.compile()
    
    def _build_task_generation_workflow(self) -> Graph:
        """Build task generation workflow (clarifier + synthesizer + taskmaster).
        
        Returns:
            LangGraph workflow
        """
        workflow = StateGraph(WorkflowState)
        
        workflow.add_node("clarifier", self._clarifier_node)
        workflow.add_node("synthesizer", self._synthesizer_node)
        workflow.add_node("taskmaster", self._taskmaster_node)
        
        workflow.set_entry_point("clarifier")
        workflow.add_edge("clarifier", "synthesizer")
        workflow.add_edge("synthesizer", "taskmaster")
        workflow.add_edge("taskmaster", END)
        
        return workflow.compile()
    
    def _build_verification_workflow(self) -> Graph:
        """Build verification-only workflow.
        
        Returns:
            LangGraph workflow
        """
        workflow = StateGraph(WorkflowState)
        
        workflow.add_node("verifier", self._verifier_node)
        workflow.set_entry_point("verifier")
        workflow.add_edge("verifier", END)
        
        return workflow.compile()
    
    async def execute_workflow(
        self,
        workflow_type: WorkflowType,
        workflow_id: str,
        user_request: str,
        user_id: Optional[int] = None,
        initial_data: Optional[Dict[str, Any]] = None
    ) -> WorkflowState:
        """Execute a workflow.
        
        Args:
            workflow_type: Type of workflow to execute
            workflow_id: Unique workflow identifier
            user_request: Original user request
            user_id: User ID if available
            initial_data: Initial data for the workflow
            
        Returns:
            Final workflow state
            
        Raises:
            ValueError: If workflow type is not supported
            Exception: If workflow execution fails
        """
        if workflow_type not in self.workflows:
            raise ValueError(f"Unsupported workflow type: {workflow_type}")
        
        self.logger.info(
            "Starting workflow execution",
            workflow_id=workflow_id,
            workflow_type=workflow_type.value,
            user_id=user_id
        )
        
        # Log workflow start
        await self.audit_service.log_workflow_start(
            workflow_id=workflow_id,
            workflow_type=workflow_type.value,
            user_request=user_request,
            user_id=user_id
        )
        
        try:
            # Initialize workflow state
            initial_state = WorkflowState(
                workflow_id=workflow_id,
                workflow_type=workflow_type,
                user_request=user_request,
                user_id=user_id,
                clarifier_output=None,
                synthesizer_output=None,
                taskmaster_output=None,
                verifier_output=None,
                current_step="",
                steps_completed=[],
                errors=[],
                metadata=initial_data or {}
            )
            
            # Get workflow graph
            workflow_graph = self.workflows[workflow_type]
            
            # Execute workflow
            final_state = await workflow_graph.ainvoke(initial_state)
            
            self.logger.info(
                "Workflow execution completed",
                workflow_id=workflow_id,
                steps_completed=len(final_state["steps_completed"]),
                errors_count=len(final_state["errors"])
            )
            
            return final_state
            
        except Exception as e:
            error_msg = f"Workflow execution failed: {str(e)}"
            self.logger.error("Workflow execution failed", workflow_id=workflow_id, error=error_msg)
            
            # Log workflow error
            await self.audit_service.log_workflow_step(
                workflow_id=workflow_id,
                step_id="workflow_error",
                step_type="error",
                step_status="failed",
                step_data={"error": error_msg}
            )
            
            raise
    
    async def _clarifier_node(self, state: WorkflowState) -> WorkflowState:
        """Execute the clarifier agent node.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state
        """
        step_id = "clarifier"
        state["current_step"] = step_id
        
        self.logger.info("Executing clarifier node", workflow_id=state["workflow_id"])
        
        try:
            # Log step start
            await self.audit_service.log_workflow_step(
                workflow_id=state["workflow_id"],
                step_id=step_id,
                step_type="agent_execution",
                step_status="started"
            )
            
            # Prepare clarifier input
            clarifier_input = {
                "request_id": f"{state['workflow_id']}_clarifier",
                "user_id": state["user_id"],
                "user_request": state["user_request"],
                "domain_context": state["metadata"].get("domain_context"),
                "existing_requirements": state["metadata"].get("existing_requirements", [])
            }
            
            # Execute clarifier
            result = await self.clarifier.execute(clarifier_input)
            
            # Parse result into schema object
            from ..schemas.agent_schemas import ClarifierOutput
            state["clarifier_output"] = ClarifierOutput(**result)
            state["steps_completed"].append(step_id)
            
            # Log step completion
            await self.audit_service.log_workflow_step(
                workflow_id=state["workflow_id"],
                step_id=step_id,
                step_type="agent_execution",
                step_status="completed",
                step_data={"confidence": result["confidence"]}
            )
            
            self.logger.info(
                "Clarifier node completed",
                workflow_id=state["workflow_id"],
                confidence=result["confidence"]
            )
            
        except Exception as e:
            error_msg = f"Clarifier node failed: {str(e)}"
            state["errors"].append(error_msg)
            
            # Log step error
            await self.audit_service.log_workflow_step(
                workflow_id=state["workflow_id"],
                step_id=step_id,
                step_type="agent_execution",
                step_status="failed",
                step_data={"error": error_msg}
            )
            
            self.logger.error("Clarifier node failed", workflow_id=state["workflow_id"], error=error_msg)
        
        return state
    
    async def _synthesizer_node(self, state: WorkflowState) -> WorkflowState:
        """Execute the synthesizer agent node.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state
        """
        step_id = "synthesizer"
        state["current_step"] = step_id
        
        self.logger.info("Executing synthesizer node", workflow_id=state["workflow_id"])
        
        try:
            # Log step start
            await self.audit_service.log_workflow_step(
                workflow_id=state["workflow_id"],
                step_id=step_id,
                step_type="agent_execution",
                step_status="started"
            )
            
            # Prepare synthesizer input
            clarified_requirements = {}
            if state["clarifier_output"]:
                # Convert clarifier output to requirements format
                clarified_requirements = {
                    "questions_and_answers": [
                        {"question": q.question, "answer": "Pending user input"}
                        for q in state["clarifier_output"].questions
                    ],
                    "identified_gaps": state["clarifier_output"].identified_gaps,
                    "assumptions": state["clarifier_output"].assumptions
                }
            else:
                # Use user request directly if no clarifier output
                clarified_requirements = {"user_request": state["user_request"]}
            
            synthesizer_input = {
                "request_id": f"{state['workflow_id']}_synthesizer",
                "user_id": state["user_id"],
                "clarified_requirements": clarified_requirements,
                "knowledge_context": [],  # Will be populated by agent
                "scope_boundaries": state["metadata"].get("scope_boundaries")
            }
            
            # Execute synthesizer
            result = await self.synthesizer.execute(synthesizer_input)
            
            # Parse result into schema object
            from ..schemas.agent_schemas import SynthesizerOutput
            state["synthesizer_output"] = SynthesizerOutput(**result)
            state["steps_completed"].append(step_id)
            
            # Log step completion
            await self.audit_service.log_workflow_step(
                workflow_id=state["workflow_id"],
                step_id=step_id,
                step_type="agent_execution",
                step_status="completed",
                step_data={"confidence": result["confidence"]}
            )
            
            self.logger.info(
                "Synthesizer node completed",
                workflow_id=state["workflow_id"],
                confidence=result["confidence"]
            )
            
        except Exception as e:
            error_msg = f"Synthesizer node failed: {str(e)}"
            state["errors"].append(error_msg)
            
            # Log step error
            await self.audit_service.log_workflow_step(
                workflow_id=state["workflow_id"],
                step_id=step_id,
                step_type="agent_execution",
                step_status="failed",
                step_data={"error": error_msg}
            )
            
            self.logger.error("Synthesizer node failed", workflow_id=state["workflow_id"], error=error_msg)
        
        return state
    
    async def _taskmaster_node(self, state: WorkflowState) -> WorkflowState:
        """Execute the taskmaster agent node.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state
        """
        step_id = "taskmaster"
        state["current_step"] = step_id
        
        self.logger.info("Executing taskmaster node", workflow_id=state["workflow_id"])
        
        try:
            # Check if synthesizer output is available
            if not state["synthesizer_output"]:
                raise ValueError("Taskmaster requires synthesizer output")
            
            # Log step start
            await self.audit_service.log_workflow_step(
                workflow_id=state["workflow_id"],
                step_id=step_id,
                step_type="agent_execution",
                step_status="started"
            )
            
            # Prepare taskmaster input
            taskmaster_input = {
                "request_id": f"{state['workflow_id']}_taskmaster",
                "user_id": state["user_id"],
                "to_be_document": state["synthesizer_output"].to_be_document.dict(),
                "gap_analysis": [gap.dict() for gap in state["synthesizer_output"].gap_analysis],
                "implementation_approach": state["synthesizer_output"].implementation_approach,
                "project_constraints": state["metadata"].get("project_constraints", {})
            }
            
            # Execute taskmaster
            result = await self.taskmaster.execute(taskmaster_input)
            
            # Parse result into schema object
            from ..schemas.agent_schemas import TaskmasterOutput
            state["taskmaster_output"] = TaskmasterOutput(**result)
            state["steps_completed"].append(step_id)
            
            # Log step completion
            await self.audit_service.log_workflow_step(
                workflow_id=state["workflow_id"],
                step_id=step_id,
                step_type="agent_execution",
                step_status="completed",
                step_data={"confidence": result["confidence"], "tasks_generated": len(result["tasks"])}
            )
            
            self.logger.info(
                "Taskmaster node completed",
                workflow_id=state["workflow_id"],
                confidence=result["confidence"],
                tasks_count=len(result["tasks"])
            )
            
        except Exception as e:
            error_msg = f"Taskmaster node failed: {str(e)}"
            state["errors"].append(error_msg)
            
            # Log step error
            await self.audit_service.log_workflow_step(
                workflow_id=state["workflow_id"],
                step_id=step_id,
                step_type="agent_execution",
                step_status="failed",
                step_data={"error": error_msg}
            )
            
            self.logger.error("Taskmaster node failed", workflow_id=state["workflow_id"], error=error_msg)
        
        return state
    
    async def _verifier_node(self, state: WorkflowState) -> WorkflowState:
        """Execute the verifier agent node.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state
        """
        step_id = "verifier"
        state["current_step"] = step_id
        
        self.logger.info("Executing verifier node", workflow_id=state["workflow_id"])
        
        try:
            # Log step start
            await self.audit_service.log_workflow_step(
                workflow_id=state["workflow_id"],
                step_id=step_id,
                step_type="agent_execution",
                step_status="started"
            )
            
            # Prepare verifier input
            verifier_input = {
                "request_id": f"{state['workflow_id']}_verifier",
                "user_id": state["user_id"],
                "clarifier_output": state["clarifier_output"].dict() if state["clarifier_output"] else None,
                "synthesizer_output": state["synthesizer_output"].dict() if state["synthesizer_output"] else None,
                "taskmaster_output": state["taskmaster_output"].dict() if state["taskmaster_output"] else None,
                "knowledge_base_context": [],  # Will be populated by agent
                "code_context": state["metadata"].get("code_context", []),
                "schema_context": state["metadata"].get("schema_context", [])
            }
            
            # Execute verifier
            result = await self.verifier.execute(verifier_input)
            
            # Parse result into schema object
            from ..schemas.agent_schemas import VerifierOutput
            state["verifier_output"] = VerifierOutput(**result)
            state["steps_completed"].append(step_id)
            
            # Log step completion
            await self.audit_service.log_workflow_step(
                workflow_id=state["workflow_id"],
                step_id=step_id,
                step_type="agent_execution",
                step_status="completed",
                step_data={
                    "confidence": result["confidence"],
                    "approval_status": result["approval_status"],
                    "validation_score": result["overall_validation"]["score"]
                }
            )
            
            self.logger.info(
                "Verifier node completed",
                workflow_id=state["workflow_id"],
                confidence=result["confidence"],
                approval_status=result["approval_status"]
            )
            
        except Exception as e:
            error_msg = f"Verifier node failed: {str(e)}"
            state["errors"].append(error_msg)
            
            # Log step error
            await self.audit_service.log_workflow_step(
                workflow_id=state["workflow_id"],
                step_id=step_id,
                step_type="agent_execution",
                step_status="failed",
                step_data={"error": error_msg}
            )
            
            self.logger.error("Verifier node failed", workflow_id=state["workflow_id"], error=error_msg)
        
        return state
    
    async def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a running workflow.
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            Workflow status or None if not found
        """
        # In a production system, this would query a persistent store
        # For now, return a placeholder
        return {
            "workflow_id": workflow_id,
            "status": "running",
            "message": "Workflow status tracking not implemented in this demo"
        }
    
    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a running workflow.
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            True if cancelled successfully
        """
        # In a production system, this would cancel the running workflow
        self.logger.info("Workflow cancellation requested", workflow_id=workflow_id)
        return True

