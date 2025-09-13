"""Shared models package for Analyst Copilot."""

from .auth import AuthResponse, LoginRequest, LoginResponse, LogoutResponse
from .common import BaseModel, ErrorResponse, HealthResponse, PaginatedResponse
from .jobs import IngestJobResponse, JobListResponse, JobStatus
from .workflows import WorkflowRequest, WorkflowResponse, WorkflowStatus

__version__ = "1.0.0"

__all__ = [
    # Auth models
    "AuthResponse",
    "LoginRequest",
    "LoginResponse",
    "LogoutResponse",
    # Common models
    "BaseModel",
    "ErrorResponse",
    "HealthResponse",
    "PaginatedResponse",
    # Job models
    "JobStatus",
    "IngestJobResponse",
    "JobListResponse",
    # Workflow models
    "WorkflowStatus",
    "WorkflowRequest",
    "WorkflowResponse",
]
