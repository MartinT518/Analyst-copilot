"""Structured logging with correlation IDs for ACP services."""

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, Optional

import structlog
from structlog.stdlib import LoggerFactory

# Context variable for correlation ID
correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


class CorrelationIDProcessor:
    """Processor to add correlation ID to log records."""

    def __call__(self, logger, method_name, event_dict):
        """Add correlation ID to event dictionary."""
        corr_id = correlation_id.get()
        if corr_id:
            event_dict["correlation_id"] = corr_id
        return event_dict


class TimestampProcessor:
    """Processor to add ISO timestamp to log records."""

    def __call__(self, logger, method_name, event_dict):
        """Add ISO timestamp to event dictionary."""
        event_dict["timestamp"] = datetime.utcnow().isoformat() + "Z"
        return event_dict


class ServiceProcessor:
    """Processor to add service information to log records."""

    def __init__(self, service_name: str, service_version: str):
        """Initialize service processor."""
        self.service_name = service_name
        self.service_version = service_version

    def __call__(self, logger, method_name, event_dict):
        """Add service information to event dictionary."""
        event_dict["service"] = self.service_name
        event_dict["version"] = self.service_version
        return event_dict


class SecurityProcessor:
    """Processor to sanitize sensitive information from logs."""

    SENSITIVE_FIELDS = {
        "password",
        "secret",
        "token",
        "key",
        "auth",
        "credential",
        "api_key",
        "access_token",
        "refresh_token",
        "authorization",
    }

    def __call__(self, logger, method_name, event_dict):
        """Sanitize sensitive fields in event dictionary."""
        for key, value in event_dict.items():
            if any(sensitive in key.lower() for sensitive in self.SENSITIVE_FIELDS):
                if isinstance(value, str) and len(value) > 8:
                    event_dict[key] = value[:4] + "*" * (len(value) - 8) + value[-4:]
                else:
                    event_dict[key] = "***REDACTED***"
        return event_dict


def setup_logging(
    service_name: str = "acp-ingest",
    service_version: str = "1.0.0",
    log_level: str = "INFO",
    log_format: str = "json",
    log_file: Optional[str] = None,
) -> None:
    """Setup structured logging for the service.

    Args:
        service_name: Name of the service
        service_version: Version of the service
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Log format (json, console)
        log_file: Optional log file path
    """

    # Configure standard library logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(message)s",
        stream=sys.stdout,
    )

    # Configure structlog processors
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        TimestampProcessor(),
        ServiceProcessor(service_name, service_version),
        CorrelationIDProcessor(),
        SecurityProcessor(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Add output processor based on format
    if log_format.lower() == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Setup file logging if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.setFormatter(logging.Formatter("%(message)s"))

        logger = logging.getLogger()
        logger.addHandler(file_handler)


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name

    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)


def set_correlation_id(corr_id: Optional[str] = None) -> str:
    """Set correlation ID for the current context.

    Args:
        corr_id: Optional correlation ID, generates new one if not provided

    Returns:
        The correlation ID
    """
    if corr_id is None:
        corr_id = str(uuid.uuid4())

    correlation_id.set(corr_id)
    return corr_id


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID.

    Returns:
        Current correlation ID or None
    """
    return correlation_id.get()


def log_request_start(
    method: str, path: str, user_id: Optional[str] = None, **kwargs
) -> str:
    """Log the start of a request.

    Args:
        method: HTTP method
        path: Request path
        user_id: Optional user ID
        **kwargs: Additional log fields

    Returns:
        Correlation ID for the request
    """
    corr_id = set_correlation_id()

    logger = get_logger("request")
    logger.info("Request started", method=method, path=path, user_id=user_id, **kwargs)

    return corr_id


def log_request_end(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    user_id: Optional[str] = None,
    **kwargs
) -> None:
    """Log the end of a request.

    Args:
        method: HTTP method
        path: Request path
        status_code: HTTP status code
        duration_ms: Request duration in milliseconds
        user_id: Optional user ID
        **kwargs: Additional log fields
    """
    logger = get_logger("request")
    logger.info(
        "Request completed",
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=duration_ms,
        user_id=user_id,
        **kwargs
    )


def log_error(
    error: Exception, context: Optional[Dict[str, Any]] = None, **kwargs
) -> None:
    """Log an error with context.

    Args:
        error: Exception that occurred
        context: Optional context information
        **kwargs: Additional log fields
    """
    logger = get_logger("error")

    error_info = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context or {},
        **kwargs,
    }

    logger.error("Error occurred", **error_info, exc_info=True)


def log_business_event(
    event_type: str, event_data: Dict[str, Any], user_id: Optional[str] = None, **kwargs
) -> None:
    """Log a business event.

    Args:
        event_type: Type of business event
        event_data: Event data
        user_id: Optional user ID
        **kwargs: Additional log fields
    """
    logger = get_logger("business")
    logger.info(
        "Business event",
        event_type=event_type,
        event_data=event_data,
        user_id=user_id,
        **kwargs
    )


def log_security_event(
    event_type: str,
    severity: str = "medium",
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    **kwargs
) -> None:
    """Log a security event.

    Args:
        event_type: Type of security event
        severity: Event severity (low, medium, high, critical)
        user_id: Optional user ID
        ip_address: Optional IP address
        **kwargs: Additional log fields
    """
    logger = get_logger("security")
    logger.warning(
        "Security event",
        event_type=event_type,
        severity=severity,
        user_id=user_id,
        ip_address=ip_address,
        **kwargs
    )


def log_performance_metric(
    metric_name: str,
    value: float,
    unit: str = "ms",
    tags: Optional[Dict[str, str]] = None,
    **kwargs
) -> None:
    """Log a performance metric.

    Args:
        metric_name: Name of the metric
        value: Metric value
        unit: Metric unit
        tags: Optional metric tags
        **kwargs: Additional log fields
    """
    logger = get_logger("metrics")
    logger.info(
        "Performance metric",
        metric_name=metric_name,
        value=value,
        unit=unit,
        tags=tags or {},
        **kwargs
    )
