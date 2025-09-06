"""LangGraph-based agent workflow orchestration."""

import asyncio
import json
import uuid
from typing import Dict, Any, List, Optional, TypedDict, Annotated
from datetime import datetime
import structlog

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from .schemas import (
    WorkflowRequest, WorkflowStatus, ClarifyingQuestions, ClientAnswers,
    ASISDocument, TOBEDocument, DeveloperTask, VerificationFlag,
    WorkflowStatus as WorkflowStatusEnum
)
from .services.llm_service import LLMService
from .services.knowledge_service import KnowledgeService
from .services.audit_service import AuditService

logger = structlog.get_logger(__name__)


class AgentState(TypedDict):
    """State for the agent workflow."""
    # Core workflow data
    job_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    
    # Input data
    initial_request: WorkflowRequest
    retrieved_context: Optional[Dict[str, Any]]
    
    # Agent outputs
    clarifying_questions: Optional[ClarifyingQuestions]
    client_answers: Optional[ClientAnswers]
    asis_document: Optional[ASISDocument]
    tobe_document: Optional[TOBEDocument]
    developer_task: Optional[DeveloperTask]
    verification_flags: List[VerificationFlag]
    
    # Workflow control
    current_step: str
    progress_percentage: int
    error_message: Optional[str]
    
    # History and metadata
    history: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    
    # Messages for LangGraph
    messages: Annotated[List[BaseMessage], add_messages]


class AgentWorkflow:
    """Main workflow orchestrator using LangGraph."""
    
    def __init__(self):
        """Initialize the workflow manager."""
        self.workflows: Dict[str, AgentState] = {}
        self.llm_service: Optional[LLMService] = None
        self.knowledge_service: Optional[KnowledgeService] = None
        self.audit_service: Optional[AuditService] = None
        self.graph: Optional[StateGraph] = None
        
    async def initialize(
        self,
        llm_service: LLMService,
        knowledge_service: KnowledgeService,
        audit_service: AuditService
    ):
        """Initialize the workflow with required services.
        
        Args:
            llm_service: LLM service for agent interactions
            knowledge_service: Knowledge service for context retrieval
            audit_service: Audit service for logging
        """
        self.llm_service = llm_service
        self.knowledge_service = knowledge_service
        self.audit_service = audit_service
        
        # Build the workflow graph
        await self._build_workflow_graph()
        
        logger.info("Agent workflow initialized successfully")
    
    async def _build_workflow_graph(self):
        """Build the LangGraph workflow."""
        # Create the state graph
        workflow = StateGraph(AgentState)
        
        # Add nodes for each agent
        workflow.add_node("context_retrieval", self._context_retrieval_node)
        workflow.add_node("clarifier", self._clarifier_node)
        workflow.add_node("synthesizer", self._synthesizer_node)
        workflow.add_node("taskmaster", self._taskmaster_node)
        workflow.add_node("verifier", self._verifier_node)
        
        # Define the workflow edges
        workflow.set_entry_point("context_retrieval")
        
        workflow.add_edge("context_retrieval", "clarifier")
        workflow.add_conditional_edges(
            "clarifier",
            self._should_continue_after_clarifier,
            {
                "wait_for_answers": END,
                "continue": "synthesizer"
            }
        )
        workflow.add_edge("synthesizer", "taskmaster")
        workflow.add_edge("taskmaster", "verifier")
        workflow.add_edge("verifier", END)
        
        # Compile the graph
        self.graph = workflow.compile()
        
        logger.info("Workflow graph built successfully")
    
    async def start_workflow(self, job_id: str, request: WorkflowRequest):
        """Start a new workflow.
        
        Args:
            job_id: Unique job identifier
            request: Workflow request
        """
        try:
            # Create initial state
            state = AgentState(
                job_id=job_id,
                status=WorkflowStatusEnum.PROCESSING,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                initial_request=request,
                retrieved_context=None,
                clarifying_questions=None,
                client_answers=None,
                asis_document=None,
                tobe_document=None,
                developer_task=None,
                verification_flags=[],
                current_step="context_retrieval",
                progress_percentage=0,
                error_message=None,
                history=[],
                metadata={},
                messages=[]
            )
            
            # Store workflow state
            self.workflows[job_id] = state
            
            # Log workflow start
            await self.audit_service.log_workflow_start(
                job_id=job_id,
                request_type=request.request_type,
                client_id=request.client_id
            )
            
            # Start workflow execution
            await self._execute_workflow(job_id)
            
        except Exception as e:
            logger.error("Failed to start workflow", job_id=job_id, error=str(e))
            if job_id in self.workflows:
                self.workflows[job_id]["error_message"] = str(e)
                self.workflows[job_id]["status"] = WorkflowStatusEnum.FAILED
    
    async def continue_workflow(self, job_id: str, answers: ClientAnswers):
        """Continue workflow with client answers.
        
        Args:
            job_id: Unique job identifier
            answers: Client answers
        """
        try:
            if job_id not in self.workflows:
                raise ValueError(f"Workflow {job_id} not found")
            
            # Update state with answers
            self.workflows[job_id]["client_answers"] = answers
            self.workflows[job_id]["status"] = WorkflowStatusEnum.PROCESSING
            self.workflows[job_id]["current_step"] = "synthesizer"
            self.workflows[job_id]["updated_at"] = datetime.utcnow()
            
            # Log answers submission
            await self.audit_service.log_workflow_answers(
                job_id=job_id,
                answers_count=len(answers.answers)
            )
            
            # Continue workflow execution
            await self._execute_workflow(job_id)
            
        except Exception as e:
            logger.error("Failed to continue workflow", job_id=job_id, error=str(e))
            if job_id in self.workflows:
                self.workflows[job_id]["error_message"] = str(e)
                self.workflows[job_id]["status"] = WorkflowStatusEnum.FAILED
    
    async def _execute_workflow(self, job_id: str):
        """Execute the workflow graph.
        
        Args:
            job_id: Unique job identifier
        """
        try:
            state = self.workflows[job_id]
            
            # Execute the workflow graph
            final_state = await self.graph.ainvoke(state)
            
            # Update stored state
            self.workflows[job_id] = final_state
            
            # Log completion
            await self.audit_service.log_workflow_complete(
                job_id=job_id,
                status=final_state["status"],
                duration_seconds=(datetime.utcnow() - final_state["created_at"]).total_seconds()
            )
            
        except Exception as e:
            logger.error("Workflow execution failed", job_id=job_id, error=str(e))
            if job_id in self.workflows:
                self.workflows[job_id]["error_message"] = str(e)
                self.workflows[job_id]["status"] = WorkflowStatusEnum.FAILED
    
    async def _context_retrieval_node(self, state: AgentState) -> AgentState:
        """Context retrieval node - searches knowledge base for relevant information."""
        try:
            logger.info("Executing context retrieval", job_id=state["job_id"])
            
            # Search knowledge base for relevant context
            search_query = self._extract_search_query(state["initial_request"])
            context_results = await self.knowledge_service.search(
                query=search_query,
                limit=10,
                filters={"source_type": ["document", "code", "schema"]}
            )
            
            # Process and structure context
            retrieved_context = {
                "search_query": search_query,
                "results": [
                    {
                        "content": result.content,
                        "source": result.source,
                        "relevance_score": result.relevance_score,
                        "metadata": result.metadata
                    }
                    for result in context_results
                ],
                "total_results": len(context_results)
            }
            
            # Update state
            state["retrieved_context"] = retrieved_context
            state["current_step"] = "clarifier"
            state["progress_percentage"] = 20
            state["updated_at"] = datetime.utcnow()
            
            # Add to history
            state["history"].append({
                "step": "context_retrieval",
                "timestamp": datetime.utcnow().isoformat(),
                "results_count": len(context_results)
            })
            
            logger.info("Context retrieval completed", job_id=state["job_id"], results_count=len(context_results))
            
        except Exception as e:
            logger.error("Context retrieval failed", job_id=state["job_id"], error=str(e))
            state["error_message"] = f"Context retrieval failed: {str(e)}"
            state["status"] = WorkflowStatusEnum.FAILED
        
        return state
    
    async def _clarifier_node(self, state: AgentState) -> AgentState:
        """Clarifier node - generates clarifying questions."""
        try:
            logger.info("Executing clarifier", job_id=state["job_id"])
            
            # Prepare context for LLM
            context_text = self._format_context_for_llm(state["retrieved_context"])
            request_text = state["initial_request"].initial_requirements
            
            # Generate clarifying questions using LLM
            system_prompt = """You are an expert business analyst specializing in requirements gathering. Your role is to generate clarifying questions to better understand the client's needs.

Given the initial request and available context, generate 3-5 high-quality clarifying questions that will help you:
1. Understand the business context and objectives
2. Clarify technical requirements and constraints
3. Identify stakeholders and their needs
4. Understand the current state and desired future state
5. Identify any assumptions or risks

Format your response as a JSON object with the following structure:
{
    "questions": [
        {
            "question_id": "q1",
            "question": "Your question here",
            "question_type": "open",
            "required": true,
            "context": "Why this question is important"
        }
    ],
    "instructions": "Instructions for the client on how to answer these questions"
}"""
            
            user_prompt = f"""Initial Request: {request_text}

Available Context:
{context_text}

Please generate clarifying questions to better understand this request."""

            response = await self.llm_service.generate_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                json_mode=True
            )
            
            # Parse response
            questions_data = json.loads(response)
            
            # Create clarifying questions object
            from .schemas import ClarifyingQuestion
            questions = [
                ClarifyingQuestion(
                    question_id=q["question_id"],
                    question=q["question"],
                    question_type=q.get("question_type", "open"),
                    required=q.get("required", True),
                    context=q.get("context")
                )
                for q in questions_data["questions"]
            ]
            
            clarifying_questions = ClarifyingQuestions(
                questions=questions,
                instructions=questions_data["instructions"]
            )
            
            # Update state
            state["clarifying_questions"] = clarifying_questions
            state["current_step"] = "waiting_for_answers"
            state["status"] = WorkflowStatusEnum.WAITING_FOR_INPUT
            state["progress_percentage"] = 40
            state["updated_at"] = datetime.utcnow()
            
            # Add to history
            state["history"].append({
                "step": "clarifier",
                "timestamp": datetime.utcnow().isoformat(),
                "questions_generated": len(questions)
            })
            
            logger.info("Clarifier completed", job_id=state["job_id"], questions_count=len(questions))
            
        except Exception as e:
            logger.error("Clarifier failed", job_id=state["job_id"], error=str(e))
            state["error_message"] = f"Clarifier failed: {str(e)}"
            state["status"] = WorkflowStatusEnum.FAILED
        
        return state
    
    async def _synthesizer_node(self, state: AgentState) -> AgentState:
        """Synthesizer node - generates AS-IS and TO-BE documents."""
        try:
            logger.info("Executing synthesizer", job_id=state["job_id"])
            
            # Prepare input for synthesis
            context_text = self._format_context_for_llm(state["retrieved_context"])
            request_text = state["initial_request"].initial_requirements
            answers_text = self._format_answers_for_llm(state["client_answers"])
            
            # Generate AS-IS document
            asis_document = await self._generate_asis_document(
                request_text, context_text, answers_text
            )
            
            # Generate TO-BE document
            tobe_document = await self._generate_tobe_document(
                request_text, context_text, answers_text, asis_document
            )
            
            # Update state
            state["asis_document"] = asis_document
            state["tobe_document"] = tobe_document
            state["current_step"] = "taskmaster"
            state["progress_percentage"] = 60
            state["updated_at"] = datetime.utcnow()
            
            # Add to history
            state["history"].append({
                "step": "synthesizer",
                "timestamp": datetime.utcnow().isoformat(),
                "asis_sections": len(asis_document.sections) if asis_document.sections else 0,
                "tobe_sections": len(tobe_document.sections) if tobe_document.sections else 0
            })
            
            logger.info("Synthesizer completed", job_id=state["job_id"])
            
        except Exception as e:
            logger.error("Synthesizer failed", job_id=state["job_id"], error=str(e))
            state["error_message"] = f"Synthesizer failed: {str(e)}"
            state["status"] = WorkflowStatusEnum.FAILED
        
        return state
    
    async def _taskmaster_node(self, state: AgentState) -> AgentState:
        """Taskmaster node - generates developer tasks."""
        try:
            logger.info("Executing taskmaster", job_id=state["job_id"])
            
            # Generate developer task using existing taskmaster agent
            from .agents.taskmaster_agent import TaskmasterAgent
            
            taskmaster = TaskmasterAgent(
                llm_service=self.llm_service,
                knowledge_service=self.knowledge_service,
                audit_service=self.audit_service
            )
            
            # Create taskmaster input
            from .schemas import TaskmasterInput
            taskmaster_input = TaskmasterInput(
                request_id=state["job_id"],
                to_be_document=state["tobe_document"],
                gap_analysis=[],  # TODO: Implement gap analysis
                implementation_approach=state["tobe_document"].implementation_approach,
                project_constraints={}
            )
            
            # Execute taskmaster
            taskmaster_output = await taskmaster.execute(taskmaster_input.dict())
            
            # Convert to developer task
            developer_task = DeveloperTask(**taskmaster_output)
            
            # Update state
            state["developer_task"] = developer_task
            state["current_step"] = "verifier"
            state["progress_percentage"] = 80
            state["updated_at"] = datetime.utcnow()
            
            # Add to history
            state["history"].append({
                "step": "taskmaster",
                "timestamp": datetime.utcnow().isoformat(),
                "user_stories_count": len(developer_task.user_stories),
                "technical_notes_count": len(developer_task.technical_notes)
            })
            
            logger.info("Taskmaster completed", job_id=state["job_id"])
            
        except Exception as e:
            logger.error("Taskmaster failed", job_id=state["job_id"], error=str(e))
            state["error_message"] = f"Taskmaster failed: {str(e)}"
            state["status"] = WorkflowStatusEnum.FAILED
        
        return state
    
    async def _verifier_node(self, state: AgentState) -> AgentState:
        """Verifier node - validates and flags issues."""
        try:
            logger.info("Executing verifier", job_id=state["job_id"])
            
            # Verify developer task against knowledge base and code analysis
            verification_flags = await self._verify_developer_task(
                state["developer_task"],
                state["retrieved_context"]
            )
            
            # Update state
            state["verification_flags"] = verification_flags
            state["current_step"] = "completed"
            state["status"] = WorkflowStatusEnum.COMPLETED
            state["progress_percentage"] = 100
            state["updated_at"] = datetime.utcnow()
            state["completed_at"] = datetime.utcnow()
            
            # Add to history
            state["history"].append({
                "step": "verifier",
                "timestamp": datetime.utcnow().isoformat(),
                "flags_count": len(verification_flags),
                "critical_flags": len([f for f in verification_flags if f.severity == "critical"])
            })
            
            logger.info("Verifier completed", job_id=state["job_id"], flags_count=len(verification_flags))
            
        except Exception as e:
            logger.error("Verifier failed", job_id=state["job_id"], error=str(e))
            state["error_message"] = f"Verifier failed: {str(e)}"
            state["status"] = WorkflowStatusEnum.FAILED
        
        return state
    
    def _should_continue_after_clarifier(self, state: AgentState) -> str:
        """Determine if workflow should continue after clarifier."""
        if state["client_answers"] is None:
            return "wait_for_answers"
        else:
            return "continue"
    
    def _extract_search_query(self, request: WorkflowRequest) -> str:
        """Extract search query from workflow request."""
        # Simple extraction - in production, this could be more sophisticated
        words = request.initial_requirements.split()[:10]  # First 10 words
        return " ".join(words)
    
    def _format_context_for_llm(self, context: Optional[Dict[str, Any]]) -> str:
        """Format retrieved context for LLM consumption."""
        if not context or not context.get("results"):
            return "No relevant context found."
        
        formatted_context = []
        for result in context["results"][:5]:  # Top 5 results
            formatted_context.append(f"Source: {result['source']}\nContent: {result['content'][:500]}...")
        
        return "\n\n".join(formatted_context)
    
    def _format_answers_for_llm(self, answers: Optional[ClientAnswers]) -> str:
        """Format client answers for LLM consumption."""
        if not answers or not answers.answers:
            return "No answers provided."
        
        formatted_answers = []
        for answer in answers.answers:
            formatted_answers.append(f"Q: {answer.question_id}\nA: {answer.answer}")
        
        return "\n\n".join(formatted_answers)
    
    async def _generate_asis_document(self, request: str, context: str, answers: str) -> ASISDocument:
        """Generate AS-IS document using LLM."""
        # Implementation for AS-IS document generation
        # This would use the LLM to analyze current state
        pass
    
    async def _generate_tobe_document(self, request: str, context: str, answers: str, asis: ASISDocument) -> TOBEDocument:
        """Generate TO-BE document using LLM."""
        # Implementation for TO-BE document generation
        # This would use the LLM to design future state
        pass
    
    async def _verify_developer_task(self, task: DeveloperTask, context: Dict[str, Any]) -> List[VerificationFlag]:
        """Verify developer task against knowledge base."""
        # Implementation for verification
        # This would check for consistency, completeness, and feasibility
        return []
    
    async def get_workflow_status(self, job_id: str) -> Optional[WorkflowStatus]:
        """Get workflow status."""
        if job_id not in self.workflows:
            return None
        
        state = self.workflows[job_id]
        return WorkflowStatus(**state)
    
    async def get_workflow_results(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow results."""
        if job_id not in self.workflows:
            return None
        
        state = self.workflows[job_id]
        
        if state["status"] != WorkflowStatusEnum.COMPLETED:
            return None
        
        return {
            "job_id": job_id,
            "status": state["status"],
            "asis_document": state["asis_document"],
            "tobe_document": state["tobe_document"],
            "developer_task": state["developer_task"],
            "verification_flags": state["verification_flags"],
            "created_at": state["created_at"],
            "completed_at": state["completed_at"]
        }
    
    async def list_workflows(self, skip: int = 0, limit: int = 10, status: str = None) -> List[Dict[str, Any]]:
        """List workflows with optional filtering."""
        workflows = list(self.workflows.values())
        
        if status:
            workflows = [w for w in workflows if w["status"] == status]
        
        # Sort by created_at descending
        workflows.sort(key=lambda x: x["created_at"], reverse=True)
        
        # Apply pagination
        return workflows[skip:skip + limit]
    
    async def health_check(self) -> bool:
        """Check workflow manager health."""
        try:
            # Check if services are available
            if not all([self.llm_service, self.knowledge_service, self.audit_service]):
                return False
            
            # Check if graph is compiled
            if not self.graph:
                return False
            
            return True
        except Exception:
            return False
    
    async def cleanup(self):
        """Cleanup workflow manager."""
        self.workflows.clear()
        self.graph = None
        logger.info("Workflow manager cleaned up")
