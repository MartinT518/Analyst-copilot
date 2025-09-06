"""Prometheus metrics for ACP services."""

import time
from typing import Optional, Dict, Any, List
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Info,
    Enum,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
    start_http_server,
)
from fastapi import Request, Response
from fastapi.responses import PlainTextResponse
import structlog

logger = structlog.get_logger(__name__)


class MetricsCollector:
    """Prometheus metrics collector for ACP services."""

    def __init__(
        self, service_name: str = "acp-ingest", service_version: str = "1.0.0"
    ):
        """Initialize metrics collector.

        Args:
            service_name: Name of the service
            service_version: Version of the service
        """
        self.service_name = service_name
        self.service_version = service_version
        self.registry = CollectorRegistry()

        # Service information
        self.service_info = Info(
            "acp_service_info", "Service information", registry=self.registry
        )
        self.service_info.info({"name": service_name, "version": service_version})

        # HTTP metrics
        self.http_requests_total = Counter(
            "acp_http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status_code", "service"],
            registry=self.registry,
        )

        self.http_request_duration = Histogram(
            "acp_http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint", "service"],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0, 100.0],
            registry=self.registry,
        )

        # Business metrics
        self.ingestion_jobs_total = Counter(
            "acp_ingestion_jobs_total",
            "Total ingestion jobs",
            ["status", "file_type", "service"],
            registry=self.registry,
        )

        self.ingestion_job_duration = Histogram(
            "acp_ingestion_job_duration_seconds",
            "Ingestion job duration in seconds",
            ["file_type", "service"],
            buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0],
            registry=self.registry,
        )

        self.vector_embeddings_total = Counter(
            "acp_vector_embeddings_total",
            "Total vector embeddings created",
            ["status", "service"],
            registry=self.registry,
        )

        self.vector_search_requests_total = Counter(
            "acp_vector_search_requests_total",
            "Total vector search requests",
            ["status", "service"],
            registry=self.registry,
        )

        self.vector_search_duration = Histogram(
            "acp_vector_search_duration_seconds",
            "Vector search duration in seconds",
            ["service"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            registry=self.registry,
        )

        # System metrics
        self.active_connections = Gauge(
            "acp_active_connections",
            "Number of active connections",
            ["connection_type", "service"],
            registry=self.registry,
        )

        self.database_connections = Gauge(
            "acp_database_connections",
            "Number of database connections",
            ["state", "service"],
            registry=self.registry,
        )

        self.redis_connections = Gauge(
            "acp_redis_connections",
            "Number of Redis connections",
            ["state", "service"],
            registry=self.registry,
        )

        # Error metrics
        self.errors_total = Counter(
            "acp_errors_total",
            "Total errors",
            ["error_type", "service"],
            registry=self.registry,
        )

        # Workflow metrics
        self.workflow_steps_total = Counter(
            "acp_workflow_steps_total",
            "Total workflow steps",
            ["workflow_type", "step", "status", "service"],
            registry=self.registry,
        )

        self.workflow_duration = Histogram(
            "acp_workflow_duration_seconds",
            "Workflow duration in seconds",
            ["workflow_type", "service"],
            buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0, 3600.0],
            registry=self.registry,
        )

        # Agent metrics
        self.agent_requests_total = Counter(
            "acp_agent_requests_total",
            "Total agent requests",
            ["agent_type", "status", "service"],
            registry=self.registry,
        )

        self.agent_duration = Histogram(
            "acp_agent_duration_seconds",
            "Agent execution duration in seconds",
            ["agent_type", "service"],
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 300.0],
            registry=self.registry,
        )

        # LLM metrics
        self.llm_requests_total = Counter(
            "acp_llm_requests_total",
            "Total LLM requests",
            ["model", "status", "service"],
            registry=self.registry,
        )

        self.llm_tokens_total = Counter(
            "acp_llm_tokens_total",
            "Total LLM tokens",
            ["model", "token_type", "service"],
            registry=self.registry,
        )

        self.llm_duration = Histogram(
            "acp_llm_duration_seconds",
            "LLM request duration in seconds",
            ["model", "service"],
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
            registry=self.registry,
        )

        logger.info("Metrics collector initialized", service_name=service_name)

    def record_http_request(
        self, method: str, endpoint: str, status_code: int, duration: float
    ) -> None:
        """Record HTTP request metrics.

        Args:
            method: HTTP method
            endpoint: Request endpoint
            status_code: HTTP status code
            duration: Request duration in seconds
        """
        self.http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code),
            service=self.service_name,
        ).inc()

        self.http_request_duration.labels(
            method=method, endpoint=endpoint, service=self.service_name
        ).observe(duration)

    def record_ingestion_job(
        self, status: str, file_type: str, duration: float
    ) -> None:
        """Record ingestion job metrics.

        Args:
            status: Job status (success, failed, cancelled)
            file_type: Type of file processed
            duration: Job duration in seconds
        """
        self.ingestion_jobs_total.labels(
            status=status, file_type=file_type, service=self.service_name
        ).inc()

        self.ingestion_job_duration.labels(
            file_type=file_type, service=self.service_name
        ).observe(duration)

    def record_vector_embedding(self, status: str) -> None:
        """Record vector embedding metrics.

        Args:
            status: Embedding status (success, failed)
        """
        self.vector_embeddings_total.labels(
            status=status, service=self.service_name
        ).inc()

    def record_vector_search(self, status: str, duration: float) -> None:
        """Record vector search metrics.

        Args:
            status: Search status (success, failed)
            duration: Search duration in seconds
        """
        self.vector_search_requests_total.labels(
            status=status, service=self.service_name
        ).inc()

        self.vector_search_duration.labels(service=self.service_name).observe(duration)

    def record_error(self, error_type: str) -> None:
        """Record error metrics.

        Args:
            error_type: Type of error
        """
        self.errors_total.labels(error_type=error_type, service=self.service_name).inc()

    def record_workflow_step(self, workflow_type: str, step: str, status: str) -> None:
        """Record workflow step metrics.

        Args:
            workflow_type: Type of workflow
            step: Workflow step
            status: Step status (success, failed, skipped)
        """
        self.workflow_steps_total.labels(
            workflow_type=workflow_type,
            step=step,
            status=status,
            service=self.service_name,
        ).inc()

    def record_workflow_duration(self, workflow_type: str, duration: float) -> None:
        """Record workflow duration metrics.

        Args:
            workflow_type: Type of workflow
            duration: Workflow duration in seconds
        """
        self.workflow_duration.labels(
            workflow_type=workflow_type, service=self.service_name
        ).observe(duration)

    def record_agent_request(
        self, agent_type: str, status: str, duration: float
    ) -> None:
        """Record agent request metrics.

        Args:
            agent_type: Type of agent
            status: Request status (success, failed)
            duration: Request duration in seconds
        """
        self.agent_requests_total.labels(
            agent_type=agent_type, status=status, service=self.service_name
        ).inc()

        self.agent_duration.labels(
            agent_type=agent_type, service=self.service_name
        ).observe(duration)

    def record_llm_request(
        self,
        model: str,
        status: str,
        duration: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        """Record LLM request metrics.

        Args:
            model: LLM model name
            status: Request status (success, failed)
            duration: Request duration in seconds
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
        """
        self.llm_requests_total.labels(
            model=model, status=status, service=self.service_name
        ).inc()

        self.llm_duration.labels(model=model, service=self.service_name).observe(
            duration
        )

        if prompt_tokens > 0:
            self.llm_tokens_total.labels(  # nosec B106 - metric labels, not passwords
                model=model,
                token_type="prompt",
                service=self.service_name,
            ).inc(prompt_tokens)

        if completion_tokens > 0:
            self.llm_tokens_total.labels(  # nosec B106 - metric labels, not passwords
                model=model,
                token_type="completion",
                service=self.service_name,
            ).inc(completion_tokens)

    def set_active_connections(self, connection_type: str, count: int) -> None:
        """Set active connections count.

        Args:
            connection_type: Type of connection
            count: Number of active connections
        """
        self.active_connections.labels(
            connection_type=connection_type, service=self.service_name
        ).set(count)

    def set_database_connections(self, state: str, count: int) -> None:
        """Set database connections count.

        Args:
            state: Connection state (active, idle, total)
            count: Number of connections
        """
        self.database_connections.labels(state=state, service=self.service_name).set(
            count
        )

    def set_redis_connections(self, state: str, count: int) -> None:
        """Set Redis connections count.

        Args:
            state: Connection state (active, idle, total)
            count: Number of connections
        """
        self.redis_connections.labels(state=state, service=self.service_name).set(count)

    def get_metrics(self) -> str:
        """Get metrics in Prometheus format.

        Returns:
            Metrics in Prometheus format
        """
        return generate_latest(self.registry).decode("utf-8")

    def start_metrics_server(self, port: int = 9090) -> None:
        """Start Prometheus metrics server.

        Args:
            port: Port to serve metrics on
        """
        try:
            start_http_server(port, registry=self.registry)
            logger.info("Prometheus metrics server started", port=port)
        except Exception as e:
            logger.error("Failed to start metrics server", port=port, error=str(e))


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance.

    Returns:
        Metrics collector instance
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def setup_metrics(
    service_name: str = "acp-ingest",
    service_version: str = "1.0.0",
    port: Optional[int] = None,
) -> MetricsCollector:
    """Setup Prometheus metrics.

    Args:
        service_name: Name of the service
        service_version: Version of the service
        port: Optional port to start metrics server on

    Returns:
        Metrics collector instance
    """
    global _metrics_collector
    _metrics_collector = MetricsCollector(service_name, service_version)

    if port:
        _metrics_collector.start_metrics_server(port)

    return _metrics_collector


def metrics_middleware(request: Request, call_next):
    """FastAPI middleware to collect HTTP metrics.

    Args:
        request: FastAPI request
        call_next: Next middleware/handler

    Returns:
        Response
    """
    start_time = time.time()

    # Get metrics collector
    metrics = get_metrics_collector()

    # Process request
    response = call_next(request)

    # Calculate duration
    duration = time.time() - start_time

    # Record metrics
    metrics.record_http_request(
        method=request.method,
        endpoint=request.url.path,
        status_code=response.status_code,
        duration=duration,
    )

    return response


def get_metrics_endpoint():
    """Get FastAPI endpoint for Prometheus metrics.

    Returns:
        FastAPI endpoint function
    """

    def metrics_endpoint():
        """Prometheus metrics endpoint."""
        metrics = get_metrics_collector()
        return PlainTextResponse(metrics.get_metrics(), media_type=CONTENT_TYPE_LATEST)

    return metrics_endpoint
