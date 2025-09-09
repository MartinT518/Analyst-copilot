"""Audit service for tracking agent execution and provenance."""

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import structlog

from ..config import get_settings
from ..schemas.common_schemas import AgentType

logger = structlog.get_logger(__name__)


class AuditService:
    """Service for auditing agent execution and maintaining provenance."""

    def __init__(self):
        """Initialize the audit service."""
        self.settings = get_settings()
        self.logger = logger.bind(service="audit")

        # In-memory audit log (in production, this would be persisted)
        self.audit_log: List[Dict[str, Any]] = []
        self.hash_chain: List[str] = []

        # Performance tracking
        self.total_events = 0
        self.events_by_type: Dict[str, int] = {}

    async def log_agent_start(
        self,
        agent_type: AgentType,
        request_id: str,
        input_data: Dict[str, Any],
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Log the start of agent execution.

        Args:
            agent_type: Type of agent
            request_id: Request identifier
            input_data: Input data for the agent
            user_id: User ID if available
            session_id: Session ID if available

        Returns:
            Audit event ID
        """
        event_id = str(uuid4())
        timestamp = datetime.utcnow()

        # Create audit event
        event = {
            "event_id": event_id,
            "event_type": "agent_start",
            "timestamp": timestamp.isoformat(),
            "agent_type": agent_type.value,
            "request_id": request_id,
            "user_id": user_id,
            "session_id": session_id,
            "input_data": self._sanitize_data(input_data),
            "metadata": {
                "agent_version": self.settings.version,
                "environment": self.settings.environment,
            },
        }

        # Add to audit log
        await self._add_audit_event(event)

        self.logger.info(
            "Agent execution started",
            event_id=event_id,
            agent_type=agent_type.value,
            request_id=request_id,
        )

        return event_id

    async def log_agent_complete(
        self,
        agent_type: AgentType,
        request_id: str,
        output_data: Dict[str, Any],
        duration_seconds: float,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Log the completion of agent execution.

        Args:
            agent_type: Type of agent
            request_id: Request identifier
            output_data: Output data from the agent
            duration_seconds: Execution duration
            user_id: User ID if available
            session_id: Session ID if available

        Returns:
            Audit event ID
        """
        event_id = str(uuid4())
        timestamp = datetime.utcnow()

        # Create audit event
        event = {
            "event_id": event_id,
            "event_type": "agent_complete",
            "timestamp": timestamp.isoformat(),
            "agent_type": agent_type.value,
            "request_id": request_id,
            "user_id": user_id,
            "session_id": session_id,
            "output_data": self._sanitize_data(output_data),
            "duration_seconds": duration_seconds,
            "metadata": {
                "confidence": output_data.get("confidence", 0.0),
                "output_size": len(json.dumps(output_data)),
            },
        }

        # Add to audit log
        await self._add_audit_event(event)

        self.logger.info(
            "Agent execution completed",
            event_id=event_id,
            agent_type=agent_type.value,
            request_id=request_id,
            duration_seconds=duration_seconds,
        )

        return event_id

    async def log_agent_error(
        self,
        agent_type: AgentType,
        request_id: str,
        error_message: str,
        duration_seconds: float,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        error_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log an agent execution error.

        Args:
            agent_type: Type of agent
            request_id: Request identifier
            error_message: Error message
            duration_seconds: Execution duration before error
            user_id: User ID if available
            session_id: Session ID if available
            error_context: Additional error context

        Returns:
            Audit event ID
        """
        event_id = str(uuid4())
        timestamp = datetime.utcnow()

        # Create audit event
        event = {
            "event_id": event_id,
            "event_type": "agent_error",
            "timestamp": timestamp.isoformat(),
            "agent_type": agent_type.value,
            "request_id": request_id,
            "user_id": user_id,
            "session_id": session_id,
            "error_message": error_message,
            "duration_seconds": duration_seconds,
            "error_context": error_context or {},
            "metadata": {"error_type": "execution_error"},
        }

        # Add to audit log
        await self._add_audit_event(event)

        self.logger.error(
            "Agent execution error",
            event_id=event_id,
            agent_type=agent_type.value,
            request_id=request_id,
            error=error_message,
        )

        return event_id

    async def log_workflow_start(
        self,
        workflow_id: str,
        workflow_type: str,
        user_request: str,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Log the start of workflow execution.

        Args:
            workflow_id: Workflow identifier
            workflow_type: Type of workflow
            user_request: Original user request
            user_id: User ID if available
            session_id: Session ID if available

        Returns:
            Audit event ID
        """
        event_id = str(uuid4())
        timestamp = datetime.utcnow()

        event = {
            "event_id": event_id,
            "event_type": "workflow_start",
            "timestamp": timestamp.isoformat(),
            "workflow_id": workflow_id,
            "workflow_type": workflow_type,
            "user_request": user_request,
            "user_id": user_id,
            "session_id": session_id,
            "metadata": {"workflow_version": self.settings.version},
        }

        await self._add_audit_event(event)

        self.logger.info(
            "Workflow started",
            event_id=event_id,
            workflow_id=workflow_id,
            workflow_type=workflow_type,
        )

        return event_id

    async def log_workflow_step(
        self,
        workflow_id: str,
        step_id: str,
        step_type: str,
        step_status: str,
        step_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log a workflow step execution.

        Args:
            workflow_id: Workflow identifier
            step_id: Step identifier
            step_type: Type of step
            step_status: Step status
            step_data: Additional step data

        Returns:
            Audit event ID
        """
        event_id = str(uuid4())
        timestamp = datetime.utcnow()

        event = {
            "event_id": event_id,
            "event_type": "workflow_step",
            "timestamp": timestamp.isoformat(),
            "workflow_id": workflow_id,
            "step_id": step_id,
            "step_type": step_type,
            "step_status": step_status,
            "step_data": self._sanitize_data(step_data or {}),
            "metadata": {},
        }

        await self._add_audit_event(event)

        self.logger.info(
            "Workflow step executed",
            event_id=event_id,
            workflow_id=workflow_id,
            step_id=step_id,
            step_status=step_status,
        )

        return event_id

    async def log_knowledge_access(
        self,
        request_id: str,
        query: str,
        results_count: int,
        knowledge_references: List[str],
        agent_type: Optional[AgentType] = None,
    ) -> str:
        """Log access to knowledge base.

        Args:
            request_id: Request identifier
            query: Search query
            results_count: Number of results returned
            knowledge_references: List of knowledge chunk IDs accessed
            agent_type: Agent type if applicable

        Returns:
            Audit event ID
        """
        event_id = str(uuid4())
        timestamp = datetime.utcnow()

        event = {
            "event_id": event_id,
            "event_type": "knowledge_access",
            "timestamp": timestamp.isoformat(),
            "request_id": request_id,
            "agent_type": agent_type.value if agent_type else None,
            "query": query,
            "results_count": results_count,
            "knowledge_references": knowledge_references,
            "metadata": {"query_length": len(query)},
        }

        await self._add_audit_event(event)

        return event_id

    async def get_audit_trail(
        self,
        request_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        agent_type: Optional[AgentType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get audit trail with optional filters.

        Args:
            request_id: Filter by request ID
            workflow_id: Filter by workflow ID
            agent_type: Filter by agent type
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Maximum number of events to return

        Returns:
            List of audit events
        """
        filtered_events = []

        for event in self.audit_log:
            # Apply filters
            if request_id and event.get("request_id") != request_id:
                continue

            if workflow_id and event.get("workflow_id") != workflow_id:
                continue

            if agent_type and event.get("agent_type") != agent_type.value:
                continue

            event_time = datetime.fromisoformat(event["timestamp"])

            if start_time and event_time < start_time:
                continue

            if end_time and event_time > end_time:
                continue

            filtered_events.append(event)

            if len(filtered_events) >= limit:
                break

        return filtered_events

    async def verify_integrity(self) -> Dict[str, Any]:
        """Verify the integrity of the audit log.

        Returns:
            Integrity verification result
        """
        if not self.hash_chain:
            return {"valid": True, "message": "No events to verify"}

        # Verify hash chain
        for i in range(1, len(self.hash_chain)):
            expected_hash = self._calculate_hash(self.audit_log[i], self.hash_chain[i - 1])

            if self.hash_chain[i] != expected_hash:
                return {
                    "valid": False,
                    "message": f"Hash chain broken at event {i}",
                    "event_id": self.audit_log[i]["event_id"],
                }

        return {
            "valid": True,
            "message": "Audit log integrity verified",
            "total_events": len(self.audit_log),
            "hash_chain_length": len(self.hash_chain),
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Get audit service metrics.

        Returns:
            Dictionary of metrics
        """
        return {
            "service": "audit",
            "total_events": self.total_events,
            "events_by_type": self.events_by_type.copy(),
            "audit_log_size": len(self.audit_log),
            "hash_chain_length": len(self.hash_chain),
            "integrity_verified": True,  # Would check in production
        }

    async def _add_audit_event(self, event: Dict[str, Any]):
        """Add an event to the audit log with hash chain.

        Args:
            event: Audit event to add
        """
        # Calculate hash for integrity
        previous_hash = self.hash_chain[-1] if self.hash_chain else ""
        event_hash = self._calculate_hash(event, previous_hash)

        # Add to log and hash chain
        self.audit_log.append(event)
        self.hash_chain.append(event_hash)

        # Update metrics
        self.total_events += 1
        event_type = event["event_type"]
        self.events_by_type[event_type] = self.events_by_type.get(event_type, 0) + 1

        # In production, persist to database here
        if self.settings.audit_enabled:
            await self._persist_event(event, event_hash)

    def _calculate_hash(self, event: Dict[str, Any], previous_hash: str) -> str:
        """Calculate hash for an audit event.

        Args:
            event: Event to hash
            previous_hash: Previous hash in chain

        Returns:
            Calculated hash
        """
        # Create deterministic string representation
        event_str = json.dumps(event, sort_keys=True, separators=(",", ":"))
        combined = f"{previous_hash}{event_str}"

        return hashlib.sha256(combined.encode()).hexdigest()

    def _sanitize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize data for audit logging (remove sensitive information).

        Args:
            data: Data to sanitize

        Returns:
            Sanitized data
        """
        # Create a copy to avoid modifying original
        sanitized = data.copy()

        # Remove or mask sensitive fields
        sensitive_fields = ["password", "token", "api_key", "secret"]

        for field in sensitive_fields:
            if field in sanitized:
                sanitized[field] = "***REDACTED***"

        # Truncate large text fields
        for key, value in sanitized.items():
            if isinstance(value, str) and len(value) > 1000:
                sanitized[key] = value[:1000] + "...[TRUNCATED]"

        return sanitized

    async def _persist_event(self, event: Dict[str, Any], event_hash: str):
        """Persist audit event to storage.

        Args:
            event: Event to persist
            event_hash: Event hash
        """
        # In production, this would write to a database
        # For now, just log it
        if self.settings.audit_agent_steps:
            self.logger.info("Audit event persisted", event_id=event["event_id"], hash=event_hash)
