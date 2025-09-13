"""Observability utilities for structured logging, metrics, and tracing."""

import json
import logging
import time
import uuid
from contextvars import ContextVar
from functools import wraps
from typing import Any, Dict, Optional, Union

import structlog
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

# Context variables for request tracking
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")

# Prometheus metrics
REQUEST_COUNT = Counter(
    "acp_requests_total",
    "Total number of requests",
    ["method", "endpoint", "status_code", "service"],
)

REQUEST_DURATION = Histogram(
    "acp_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint", "service"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

ERROR_COUNT = Counter("acp_errors_total", "Total number of errors", ["error_type", "service"])

ACTIVE_CONNECTIONS = Gauge("acp_active_connections", "Number of active connections", ["service"])

PROCESSING_TIME = Histogram(
    "acp_processing_time_seconds",
    "Time spent processing requests",
    ["operation", "service"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

QUEUE_SIZE = Gauge("acp_queue_size", "Current queue size", ["queue_name", "service"])

INGESTION_COUNT = Counter(
    "acp_ingestion_total", "Total number of documents ingested", ["file_type", "status", "service"]
)

VECTOR_OPERATIONS = Counter(
    "acp_vector_operations_total",
    "Total number of vector operations",
    ["operation", "status", "service"],
)


class StructuredLogger:
    """Structured logger with request context."""

    def __init__(self, service_name: str, log_level: str = "INFO"):
        self.service_name = service_name

        # Configure structlog
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                self._add_request_context,
                (
                    structlog.dev.ConsoleRenderer()
                    if log_level == "DEBUG"
                    else structlog.processors.JSONRenderer()
                ),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(
                getattr(logging, log_level.upper())
            ),
            logger_factory=structlog.WriteLoggerFactory(),
            cache_logger_on_first_use=True,
        )

        self.logger = structlog.get_logger()

    def _add_request_context(self, logger, method_name, event_dict):
        """Add request context to log entries."""
        event_dict["service"] = self.service_name

        request_id = request_id_var.get("")
        if request_id:
            event_dict["request_id"] = request_id

        correlation_id = correlation_id_var.get("")
        if correlation_id:
            event_dict["correlation_id"] = correlation_id

        user_id = user_id_var.get("")
        if user_id:
            event_dict["user_id"] = user_id

        # Add trace context if available
        span = trace.get_current_span()
        if span.is_recording():
            span_context = span.get_span_context()
            event_dict["trace_id"] = format(span_context.trace_id, "032x")
            event_dict["span_id"] = format(span_context.span_id, "016x")

        return event_dict

    def info(self, message: str, **kwargs):
        """Log info message."""
        self.logger.info(message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message."""
        self.logger.error(message, **kwargs)
        ERROR_COUNT.labels(
            error_type=kwargs.get("error_type", "unknown"), service=self.service_name
        ).inc()

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self.logger.warning(message, **kwargs)

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self.logger.debug(message, **kwargs)


class MetricsCollector:
    """Metrics collection utilities."""

    def __init__(self, service_name: str):
        self.service_name = service_name

    def record_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Record request metrics."""
        REQUEST_COUNT.labels(
            method=method, endpoint=endpoint, status_code=status_code, service=self.service_name
        ).inc()

        REQUEST_DURATION.labels(
            method=method, endpoint=endpoint, service=self.service_name
        ).observe(duration)

    def record_processing_time(self, operation: str, duration: float):
        """Record processing time metrics."""
        PROCESSING_TIME.labels(operation=operation, service=self.service_name).observe(duration)

    def set_active_connections(self, count: int):
        """Set active connections gauge."""
        ACTIVE_CONNECTIONS.labels(service=self.service_name).set(count)

    def set_queue_size(self, queue_name: str, size: int):
        """Set queue size gauge."""
        QUEUE_SIZE.labels(queue_name=queue_name, service=self.service_name).set(size)

    def record_ingestion(self, file_type: str, status: str):
        """Record document ingestion."""
        INGESTION_COUNT.labels(file_type=file_type, status=status, service=self.service_name).inc()

    def record_vector_operation(self, operation: str, status: str):
        """Record vector operation."""
        VECTOR_OPERATIONS.labels(
            operation=operation, status=status, service=self.service_name
        ).inc()


class TracingManager:
    """OpenTelemetry tracing manager."""

    def __init__(self, service_name: str, jaeger_endpoint: Optional[str] = None):
        self.service_name = service_name

        # Set up tracer provider
        trace.set_tracer_provider(TracerProvider())
        tracer_provider = trace.get_tracer_provider()

        # Configure Jaeger exporter if endpoint provided
        if jaeger_endpoint:
            jaeger_exporter = JaegerExporter(
                agent_host_name="localhost",
                agent_port=14268,
                collector_endpoint=jaeger_endpoint,
            )

            span_processor = BatchSpanProcessor(jaeger_exporter)
            tracer_provider.add_span_processor(span_processor)

        # Set up B3 propagation
        set_global_textmap(B3MultiFormat())

        self.tracer = trace.get_tracer(service_name)

    def instrument_fastapi(self, app):
        """Instrument FastAPI application."""
        FastAPIInstrumentor.instrument_app(app)

    def instrument_requests(self):
        """Instrument requests library."""
        RequestsInstrumentor().instrument()

    def instrument_sqlalchemy(self, engine):
        """Instrument SQLAlchemy engine."""
        SQLAlchemyInstrumentor().instrument(engine=engine)

    def start_span(self, name: str, **kwargs):
        """Start a new span."""
        return self.tracer.start_span(name, **kwargs)


def setup_observability(
    service_name: str, log_level: str = "INFO", jaeger_endpoint: Optional[str] = None
) -> tuple[StructuredLogger, MetricsCollector, TracingManager]:
    """Set up observability for a service."""

    logger = StructuredLogger(service_name, log_level)
    metrics = MetricsCollector(service_name)
    tracing = TracingManager(service_name, jaeger_endpoint)

    # Instrument common libraries
    tracing.instrument_requests()

    return logger, metrics, tracing


def generate_request_id() -> str:
    """Generate a unique request ID."""
    return str(uuid.uuid4())


def generate_correlation_id() -> str:
    """Generate a unique correlation ID."""
    return str(uuid.uuid4())


def set_request_context(request_id: str, correlation_id: str = None, user_id: str = None):
    """Set request context variables."""
    request_id_var.set(request_id)

    if correlation_id:
        correlation_id_var.set(correlation_id)

    if user_id:
        user_id_var.set(user_id)


def get_request_context() -> Dict[str, str]:
    """Get current request context."""
    return {
        "request_id": request_id_var.get(""),
        "correlation_id": correlation_id_var.get(""),
        "user_id": user_id_var.get(""),
    }


def timed_operation(operation_name: str, metrics_collector: MetricsCollector):
    """Decorator to time operations and record metrics."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                metrics_collector.record_processing_time(operation_name, duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                metrics_collector.record_processing_time(f"{operation_name}_error", duration)
                raise

        return wrapper

    return decorator


def traced_operation(operation_name: str, tracer: trace.Tracer):
    """Decorator to trace operations."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(operation_name) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise

        return wrapper

    return decorator


def get_metrics_handler():
    """Get Prometheus metrics handler for FastAPI."""

    def metrics_endpoint():
        return generate_latest()

    return metrics_endpoint


class ObservabilityMiddleware:
    """FastAPI middleware for observability."""

    def __init__(self, app, service_name: str):
        self.app = app
        self.service_name = service_name
        self.logger = StructuredLogger(service_name)
        self.metrics = MetricsCollector(service_name)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Generate request ID
        request_id = generate_request_id()
        correlation_id = None

        # Extract correlation ID from headers
        headers = dict(scope.get("headers", []))
        if b"x-correlation-id" in headers:
            correlation_id = headers[b"x-correlation-id"].decode()
        else:
            correlation_id = generate_correlation_id()

        # Set request context
        set_request_context(request_id, correlation_id)

        start_time = time.time()
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                # Add correlation ID to response headers
                headers = list(message.get("headers", []))
                headers.append([b"x-correlation-id", correlation_id.encode()])
                headers.append([b"x-request-id", request_id.encode()])
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            self.logger.error("Request failed", error=str(e), error_type=type(e).__name__)
            raise
        finally:
            # Record metrics
            duration = time.time() - start_time
            method = scope.get("method", "")
            path = scope.get("path", "")

            self.metrics.record_request(method, path, status_code, duration)

            # Log request
            self.logger.info(
                "Request completed",
                method=method,
                path=path,
                status_code=status_code,
                duration=duration,
            )
