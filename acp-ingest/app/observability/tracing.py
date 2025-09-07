"""OpenTelemetry distributed tracing for ACP services."""

import os
from typing import Any, Dict, Optional

import structlog
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode

logger = structlog.get_logger(__name__)


class TracingConfig:
    """Configuration for OpenTelemetry tracing."""

    def __init__(
        self,
        service_name: str = "acp-ingest",
        service_version: str = "1.0.0",
        jaeger_endpoint: Optional[str] = None,
        otlp_endpoint: Optional[str] = None,
        environment: str = "development",
    ):
        """Initialize tracing configuration.

        Args:
            service_name: Name of the service
            service_version: Version of the service
            jaeger_endpoint: Jaeger collector endpoint
            otlp_endpoint: OTLP collector endpoint
            environment: Environment name
        """
        self.service_name = service_name
        self.service_version = service_version
        self.jaeger_endpoint = jaeger_endpoint
        self.otlp_endpoint = otlp_endpoint
        self.environment = environment


class TracingManager:
    """Manager for OpenTelemetry tracing."""

    def __init__(self, config: TracingConfig):
        """Initialize tracing manager."""
        self.config = config
        self.tracer = None
        self._setup_tracing()

    def _setup_tracing(self) -> None:
        """Setup OpenTelemetry tracing."""
        try:
            # Create resource
            resource = Resource.create(
                {
                    "service.name": self.config.service_name,
                    "service.version": self.config.service_version,
                    "service.namespace": "acp",
                    "deployment.environment": self.config.environment,
                }
            )

            # Create tracer provider
            tracer_provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(tracer_provider)

            # Setup exporters
            if self.config.jaeger_endpoint:
                self._setup_jaeger_exporter(tracer_provider)

            if self.config.otlp_endpoint:
                self._setup_otlp_exporter(tracer_provider)

            # Get tracer
            self.tracer = trace.get_tracer(
                self.config.service_name, self.config.service_version
            )

            logger.info(
                "OpenTelemetry tracing initialized",
                service_name=self.config.service_name,
                jaeger_endpoint=self.config.jaeger_endpoint,
                otlp_endpoint=self.config.otlp_endpoint,
            )

        except Exception as e:
            logger.error("Failed to initialize OpenTelemetry tracing", error=str(e))
            # Create a no-op tracer if setup fails
            self.tracer = trace.NoOpTracer()

    def _setup_jaeger_exporter(self, tracer_provider: TracerProvider) -> None:
        """Setup Jaeger exporter."""
        try:
            jaeger_exporter = JaegerExporter(
                agent_host_name=os.getenv("JAEGER_AGENT_HOST", "localhost"),
                agent_port=int(os.getenv("JAEGER_AGENT_PORT", "6831")),
                collector_endpoint=self.config.jaeger_endpoint,
            )

            span_processor = BatchSpanProcessor(jaeger_exporter)
            tracer_provider.add_span_processor(span_processor)

            logger.info(
                "Jaeger exporter configured", endpoint=self.config.jaeger_endpoint
            )

        except Exception as e:
            logger.error("Failed to setup Jaeger exporter", error=str(e))

    def _setup_otlp_exporter(self, tracer_provider: TracerProvider) -> None:
        """Setup OTLP exporter."""
        try:
            otlp_exporter = OTLPSpanExporter(endpoint=self.config.otlp_endpoint)
            span_processor = BatchSpanProcessor(otlp_exporter)
            tracer_provider.add_span_processor(span_processor)

            logger.info("OTLP exporter configured", endpoint=self.config.otlp_endpoint)

        except Exception as e:
            logger.error("Failed to setup OTLP exporter", error=str(e))

    def instrument_fastapi(self, app) -> None:
        """Instrument FastAPI application."""
        try:
            FastAPIInstrumentor.instrument_app(
                app, tracer_provider=trace.get_tracer_provider()
            )
            logger.info("FastAPI instrumentation enabled")
        except Exception as e:
            logger.error("Failed to instrument FastAPI", error=str(e))

    def instrument_httpx(self) -> None:
        """Instrument HTTPX client."""
        try:
            HTTPXClientInstrumentor().instrument()
            logger.info("HTTPX instrumentation enabled")
        except Exception as e:
            logger.error("Failed to instrument HTTPX", error=str(e))

    def instrument_sqlalchemy(self) -> None:
        """Instrument SQLAlchemy."""
        try:
            SQLAlchemyInstrumentor().instrument()
            logger.info("SQLAlchemy instrumentation enabled")
        except Exception as e:
            logger.error("Failed to instrument SQLAlchemy", error=str(e))

    def instrument_redis(self) -> None:
        """Instrument Redis."""
        try:
            RedisInstrumentor().instrument()
            logger.info("Redis instrumentation enabled")
        except Exception as e:
            logger.error("Failed to instrument Redis", error=str(e))

    def instrument_psycopg2(self) -> None:
        """Instrument Psycopg2."""
        try:
            Psycopg2Instrumentor().instrument()
            logger.info("Psycopg2 instrumentation enabled")
        except Exception as e:
            logger.error("Failed to instrument Psycopg2", error=str(e))

    def instrument_celery(self) -> None:
        """Instrument Celery."""
        try:
            CeleryInstrumentor().instrument()
            logger.info("Celery instrumentation enabled")
        except Exception as e:
            logger.error("Failed to instrument Celery", error=str(e))

    def instrument_all(self) -> None:
        """Instrument all available libraries."""
        self.instrument_httpx()
        self.instrument_sqlalchemy()
        self.instrument_redis()
        self.instrument_psycopg2()
        self.instrument_celery()

    def get_tracer(self):
        """Get the tracer instance."""
        return self.tracer


def setup_tracing(
    service_name: str = "acp-ingest",
    service_version: str = "1.0.0",
    jaeger_endpoint: Optional[str] = None,
    otlp_endpoint: Optional[str] = None,
    environment: str = "development",
) -> TracingManager:
    """Setup OpenTelemetry tracing.

    Args:
        service_name: Name of the service
        service_version: Version of the service
        jaeger_endpoint: Jaeger collector endpoint
        otlp_endpoint: OTLP collector endpoint
        environment: Environment name

    Returns:
        Tracing manager instance
    """
    config = TracingConfig(
        service_name=service_name,
        service_version=service_version,
        jaeger_endpoint=jaeger_endpoint,
        otlp_endpoint=otlp_endpoint,
        environment=environment,
    )

    return TracingManager(config)


def trace_function(
    operation_name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None
):
    """Decorator to trace function execution.

    Args:
        operation_name: Optional operation name
        attributes: Optional span attributes

    Returns:
        Decorator function
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            span_name = operation_name or f"{func.__module__}.{func.__name__}"

            with tracer.start_as_current_span(span_name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.set_attribute("error", True)
                    span.set_attribute("error.message", str(e))
                    raise

        return wrapper

    return decorator


def trace_async_function(
    operation_name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None
):
    """Decorator to trace async function execution.

    Args:
        operation_name: Optional operation name
        attributes: Optional span attributes

    Returns:
        Decorator function
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            span_name = operation_name or f"{func.__module__}.{func.__name__}"

            with tracer.start_as_current_span(span_name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                try:
                    result = await func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.set_attribute("error", True)
                    span.set_attribute("error.message", str(e))
                    raise

        return wrapper

    return decorator


def add_span_attribute(key: str, value: Any) -> None:
    """Add attribute to current span.

    Args:
        key: Attribute key
        value: Attribute value
    """
    span = trace.get_current_span()
    if span and span.is_recording():
        span.set_attribute(key, value)


def add_span_event(name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
    """Add event to current span.

    Args:
        name: Event name
        attributes: Optional event attributes
    """
    span = trace.get_current_span()
    if span and span.is_recording():
        span.add_event(name, attributes or {})


def set_span_status(status: Status) -> None:
    """Set status of current span.

    Args:
        status: Span status
    """
    span = trace.get_current_span()
    if span and span.is_recording():
        span.set_status(status)
