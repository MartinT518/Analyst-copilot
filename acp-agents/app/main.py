"""Main FastAPI application for ACP Agents service."""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime

import structlog
import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .schemas import (
    ClientAnswers,
    WorkflowRequest,
    WorkflowResponse,
    WorkflowStatus,
)
from .services.audit_service import AuditService
from .services.knowledge_service import KnowledgeService
from .services.llm_service import LLMService
from .workflow import AgentWorkflow

# Setup logging
settings = get_settings()
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Global workflow manager
workflow_manager = AgentWorkflow()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting ACP Agents service")

    # Initialize services
    try:
        llm_service = LLMService()
        knowledge_service = KnowledgeService()
        audit_service = AuditService()

        await workflow_manager.initialize(
            llm_service=llm_service,
            knowledge_service=knowledge_service,
            audit_service=audit_service,
        )
        logger.info("Agent workflow manager initialized")
    except Exception as e:
        logger.error("Failed to initialize services", error=str(e))
        raise

    logger.info("ACP Agents service startup completed")

    yield

    # Shutdown
    logger.info("Shutting down ACP Agents service")
    await workflow_manager.cleanup()


# Create FastAPI application
app = FastAPI(
    title="ACP Agents Service",
    description="AI agent orchestration service for business analysis workflows",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)

# Add trusted host middleware for production
if not settings.debug:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"],  # Configure appropriately for production
    )


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    """Global exception handler."""
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )

    if settings.debug:
        return JSONResponse(
            status_code=500,
            content={
                "detail": str(exc),
                "type": type(exc).__name__,
                "path": request.url.path,
            },
        )
    else:
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# HTTP exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """HTTP exception handler."""
    logger.warning(
        "HTTP exception",
        path=request.url.path,
        method=request.method,
        status_code=exc.status_code,
        detail=exc.detail,
    )

    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "ACP Agents Service",
        "version": "1.0.0",
        "status": "running",
        "docs_url": "/docs" if settings.debug else None,
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check workflow manager health
        workflow_healthy = await workflow_manager.health_check()

        return {
            "status": "healthy" if workflow_healthy else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "workflow_manager": workflow_healthy,
        }
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )


# API info endpoint
@app.get("/api/v1/info")
async def api_info():
    """API information endpoint."""
    return {
        "api_version": "v1",
        "service": "ACP Agents Service",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "workflows": "/api/v1/jobs",
            "workflow_status": "/api/v1/jobs/{job_id}",
            "submit_answers": "/api/v1/jobs/{job_id}/answers",
        },
        "supported_workflows": [
            "business_analysis",
            "requirements_gathering",
            "developer_task_generation",
        ],
    }


# Start new workflow
@app.post("/api/v1/jobs", response_model=WorkflowResponse)
async def start_workflow(request: WorkflowRequest, background_tasks: BackgroundTasks):
    """Start a new agent workflow.

    Args:
        request: Workflow request with initial requirements
        background_tasks: Background tasks for async processing

    Returns:
        WorkflowResponse: Initial workflow state with clarifying questions
    """
    try:
        # Generate unique job ID
        job_id = str(uuid.uuid4())

        logger.info("Starting new workflow", job_id=job_id, request_type=request.request_type)

        # Start workflow in background
        background_tasks.add_task(workflow_manager.start_workflow, job_id=job_id, request=request)

        # Return initial response
        return WorkflowResponse(
            job_id=job_id,
            status=WorkflowStatus.PENDING,
            message="Workflow started successfully",
            clarifying_questions=None,  # Will be populated by Clarifier agent
            estimated_completion=None,
        )

    except Exception as e:
        logger.error("Failed to start workflow", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to start workflow: {str(e)}")


# Get workflow status
@app.get("/api/v1/jobs/{job_id}", response_model=WorkflowStatus)
async def get_workflow_status(job_id: str):
    """Get the status of a workflow.

    Args:
        job_id: Unique workflow identifier

    Returns:
        WorkflowStatus: Current workflow state and progress
    """
    try:
        status = await workflow_manager.get_workflow_status(job_id)

        if not status:
            raise HTTPException(status_code=404, detail="Workflow not found")

        return status

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get workflow status", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get workflow status: {str(e)}")


# Submit client answers
@app.post("/api/v1/jobs/{job_id}/answers", response_model=WorkflowResponse)
async def submit_answers(job_id: str, answers: ClientAnswers, background_tasks: BackgroundTasks):
    """Submit client answers to continue workflow.

    Args:
        job_id: Unique workflow identifier
        answers: Client answers to clarifying questions
        background_tasks: Background tasks for async processing

    Returns:
        WorkflowResponse: Updated workflow state
    """
    try:
        logger.info(
            "Submitting client answers",
            job_id=job_id,
            answers_count=len(answers.answers),
        )

        # Continue workflow with answers
        background_tasks.add_task(
            workflow_manager.continue_workflow, job_id=job_id, answers=answers
        )

        # Return updated response
        return WorkflowResponse(
            job_id=job_id,
            status=WorkflowStatus.PROCESSING,
            message="Answers submitted, processing workflow",
            clarifying_questions=None,
            estimated_completion=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error("Failed to submit answers", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to submit answers: {str(e)}")


# Get workflow results
@app.get("/api/v1/jobs/{job_id}/results")
async def get_workflow_results(job_id: str):
    """Get the final results of a completed workflow.

    Args:
        job_id: Unique workflow identifier

    Returns:
        Dict containing workflow results
    """
    try:
        results = await workflow_manager.get_workflow_results(job_id)

        if not results:
            raise HTTPException(status_code=404, detail="Workflow not found or not completed")

        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get workflow results", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get workflow results: {str(e)}")


# List workflows
@app.get("/api/v1/jobs")
async def list_workflows(skip: int = 0, limit: int = 10, status: str = None):
    """List workflows with optional filtering.

    Args:
        skip: Number of workflows to skip
        limit: Maximum number of workflows to return
        status: Filter by workflow status

    Returns:
        List of workflows
    """
    try:
        workflows = await workflow_manager.list_workflows(skip=skip, limit=limit, status=status)

        return {
            "workflows": workflows,
            "total": len(workflows),
            "skip": skip,
            "limit": limit,
        }

    except Exception as e:
        logger.error("Failed to list workflows", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list workflows: {str(e)}")


if __name__ == "__main__":
    # Run with uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,  # nosec B104 - configurable via settings
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=True,
    )
