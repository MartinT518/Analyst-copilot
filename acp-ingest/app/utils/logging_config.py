"""Logging configuration for the ACP Ingest service."""

import logging
import logging.config
import os
from datetime import datetime
from typing import Any, Dict, Optional

import structlog


def setup_logging(
    log_level: str = "INFO", log_format: str = "json", log_file: Optional[str] = None
) -> None:
    """
    Setup logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Log format (json or text)
        log_file: Optional log file path
    """
    # Configure structlog
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
            (
                structlog.processors.JSONRenderer()
                if log_format == "json"
                else structlog.dev.ConsoleRenderer()
            ),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Create logging configuration
    config = create_logging_config(log_level, log_format, log_file)

    # Apply configuration
    logging.config.dictConfig(config)

    # Set up root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))


def create_logging_config(
    log_level: str = "INFO", log_format: str = "json", log_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create logging configuration dictionary.

    Args:
        log_level: Logging level
        log_format: Log format
        log_file: Optional log file path

    Returns:
        Dict[str, Any]: Logging configuration
    """
    # Define formatters
    formatters = {
        "json": {
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
        },
        "text": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "detailed": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    }

    # Define handlers
    handlers = {
        "console": {
            "class": "logging.StreamHandler",
            "level": log_level.upper(),
            "formatter": log_format,
            "stream": "ext://sys.stdout",
        }
    }

    # Add file handler if specified
    if log_file:
        # Ensure log directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": log_level.upper(),
            "formatter": log_format,
            "filename": log_file,
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "encoding": "utf8",
        }

    # Define loggers
    loggers = {
        "": {  # Root logger
            "level": log_level.upper(),
            "handlers": list(handlers.keys()),
            "propagate": False,
        },
        "uvicorn": {"level": "INFO", "handlers": ["console"], "propagate": False},
        "uvicorn.error": {"level": "INFO", "handlers": ["console"], "propagate": False},
        "uvicorn.access": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "sqlalchemy": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        "httpx": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        "chromadb": {"level": "WARNING", "handlers": ["console"], "propagate": False},
    }

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatters,
        "handlers": handlers,
        "loggers": loggers,
    }


class ContextualLogger:
    """Contextual logger that adds request context to log messages."""

    def __init__(self, name: str):
        self.logger = structlog.get_logger(name)
        self.context = {}

    def bind(self, **kwargs):
        """Bind context to logger."""
        self.context.update(kwargs)
        return self

    def unbind(self, *keys):
        """Remove context keys."""
        for key in keys:
            self.context.pop(key, None)
        return self

    def clear_context(self):
        """Clear all context."""
        self.context.clear()
        return self

    def debug(self, message, **kwargs):
        """Log debug message with context."""
        self.logger.debug(message, **{**self.context, **kwargs})

    def info(self, message, **kwargs):
        """Log info message with context."""
        self.logger.info(message, **{**self.context, **kwargs})

    def warning(self, message, **kwargs):
        """Log warning message with context."""
        self.logger.warning(message, **{**self.context, **kwargs})

    def error(self, message, **kwargs):
        """Log error message with context."""
        self.logger.error(message, **{**self.context, **kwargs})

    def critical(self, message, **kwargs):
        """Log critical message with context."""
        self.logger.critical(message, **{**self.context, **kwargs})


class RequestLogger:
    """Logger for HTTP requests."""

    def __init__(self):
        self.logger = structlog.get_logger("request")

    def log_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        **kwargs,
    ):
        """Log HTTP request."""
        self.logger.info(
            "HTTP request",
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            **kwargs,
        )

    def log_error(
        self,
        method: str,
        path: str,
        error: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        **kwargs,
    ):
        """Log HTTP request error."""
        self.logger.error(
            "HTTP request error",
            method=method,
            path=path,
            error=error,
            user_id=user_id,
            ip_address=ip_address,
            **kwargs,
        )


class AuditLogger:
    """Logger for audit events."""

    def __init__(self):
        self.logger = structlog.get_logger("audit")

    def log_event(
        self,
        action: str,
        user_id: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Dict[str, Any] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        **kwargs,
    ):
        """Log audit event."""
        self.logger.info(
            "Audit event",
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=datetime.utcnow().isoformat(),
            **kwargs,
        )

    def log_security_event(
        self,
        event_type: str,
        severity: str,
        description: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Dict[str, Any] = None,
        **kwargs,
    ):
        """Log security event."""
        self.logger.warning(
            "Security event",
            event_type=event_type,
            severity=severity,
            description=description,
            user_id=user_id,
            ip_address=ip_address,
            details=details or {},
            timestamp=datetime.utcnow().isoformat(),
            **kwargs,
        )


class PerformanceLogger:
    """Logger for performance metrics."""

    def __init__(self):
        self.logger = structlog.get_logger("performance")

    def log_operation(
        self,
        operation: str,
        duration_ms: float,
        success: bool = True,
        details: Dict[str, Any] = None,
        **kwargs,
    ):
        """Log operation performance."""
        self.logger.info(
            "Operation performance",
            operation=operation,
            duration_ms=duration_ms,
            success=success,
            details=details or {},
            **kwargs,
        )

    def log_database_query(
        self, query_type: str, table: str, duration_ms: float, rows_affected: int = None, **kwargs
    ):
        """Log database query performance."""
        self.logger.debug(
            "Database query",
            query_type=query_type,
            table=table,
            duration_ms=duration_ms,
            rows_affected=rows_affected,
            **kwargs,
        )

    def log_external_api_call(
        self,
        service: str,
        endpoint: str,
        method: str,
        status_code: int,
        duration_ms: float,
        **kwargs,
    ):
        """Log external API call performance."""
        self.logger.info(
            "External API call",
            service=service,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms,
            **kwargs,
        )


def get_logger(name: str) -> ContextualLogger:
    """
    Get a contextual logger instance.

    Args:
        name: Logger name

    Returns:
        ContextualLogger: Logger instance
    """
    return ContextualLogger(name)


def get_request_logger() -> RequestLogger:
    """Get request logger instance."""
    return RequestLogger()


def get_audit_logger() -> AuditLogger:
    """Get audit logger instance."""
    return AuditLogger()


def get_performance_logger() -> PerformanceLogger:
    """Get performance logger instance."""
    return PerformanceLogger()


class LoggingMiddleware:
    """Middleware for logging HTTP requests."""

    def __init__(self):
        self.request_logger = get_request_logger()

    async def __call__(self, request, call_next):
        """Process request and log details."""
        import time

        start_time = time.time()

        # Extract request details
        method = request.method
        path = request.url.path
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Log successful request
            self.request_logger.log_request(
                method=method,
                path=path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            return response

        except Exception as e:
            # Log error
            self.request_logger.log_error(
                method=method, path=path, error=str(e), ip_address=ip_address
            )
            raise


def configure_third_party_loggers():
    """Configure third-party library loggers."""
    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)

    # Database loggers
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.INFO)

    # Vector database loggers
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

    # ML/AI library loggers
    logging.getLogger("transformers").setLevel(logging.WARNING)
    logging.getLogger("torch").setLevel(logging.WARNING)
    logging.getLogger("tensorflow").setLevel(logging.WARNING)
