"""Enhanced FastAPI application for ACP Ingest service with Phase 0 foundation."""

import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from .api import health, ingest, search
from .auth.oauth2 import get_auth_manager
from .config import get_settings
from .database import Base, engine
from .observability.logging import (
    get_logger,
    log_request_end,
    log_request_start,
    setup_logging,
)
from .observability.metrics import (
    get_metrics_endpoint,
    metrics_middleware,
    setup_metrics,
)
from .observability.tracing import setup_tracing
from .security_config import get_security_config
from .utils.file_utils import ensure_directory

# Initialize security configuration with fail-fast validation
try:
    security_config = get_security_config()
    settings = get_settings()
except Exception as e:
    print(f"CRITICAL: Security configuration validation failed: {e}")
    print("System cannot start with invalid security configuration.")
    exit(1)

# Setup structured logging with correlation IDs
setup_logging(
    service_name="acp-ingest",
    service_version="1.0.0",
    log_level=settings.LOG_LEVEL,
    log_format=settings.LOG_FORMAT,
    log_file=settings.LOG_FILE,
)

logger = get_logger(__name__)

# Setup OpenTelemetry tracing
tracing_manager = setup_tracing(
    service_name="acp-ingest",
    service_version="1.0.0",
    jaeger_endpoint=os.getenv("OTEL_EXPORTER_JAEGER_ENDPOINT"),
    otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
    environment=settings.ENVIRONMENT,
)

# Setup Prometheus metrics
metrics_collector = setup_metrics(
    service_name="acp-ingest",
    service_version="1.0.0",
    port=(
        int(os.getenv("PROMETHEUS_PORT", "9090"))
        if os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true"
        else None
    ),
)

# Initialize authentication manager
auth_manager = get_auth_manager(security_config)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with comprehensive initialization."""
    # Startup
    logger.info("Starting ACP Ingest service with Phase 0 foundation")

    # Validate security configuration
    security_errors = security_config.validate_production_security()
    if security_errors:
        error_msg = "Security validation failed:\n" + "\n".join(
            f"- {error}" for error in security_errors
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Create database tables
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error("Failed to create database tables", error=str(e))
        raise

    # Ensure required directories exist
    ensure_directory(settings.UPLOAD_DIR)
    ensure_directory(
        os.path.dirname(settings.LOG_FILE) if settings.LOG_FILE else "/app/logs"
    )
    logger.info("Required directories created/verified")

    # Initialize observability
    try:
        # Instrument FastAPI with OpenTelemetry
        tracing_manager.instrument_fastapi(app)
        tracing_manager.instrument_all()
        logger.info("OpenTelemetry instrumentation enabled")
    except Exception as e:
        logger.error("Failed to setup OpenTelemetry", error=str(e))
        # Don't fail startup if tracing fails

    logger.info("ACP Ingest service startup completed successfully")

    yield

    # Shutdown
    logger.info("Shutting down ACP Ingest service")


# Create FastAPI application
app = FastAPI(
    title="ACP Ingest Service",
    description="Secure ingestion and knowledge management service for Analyst Copilot",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Add security middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=security_config.cors_origins,
    allow_credentials=True,
    allow_methods=security_config.cors_methods,
    allow_headers=security_config.cors_headers,
)

# Add trusted host middleware for production
if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"],  # Configure appropriately for production
    )

# Add metrics middleware
app.middleware("http")(metrics_middleware)


# Request logging middleware
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Middleware to log requests with correlation IDs."""
    start_time = time.time()

    # Generate correlation ID
    correlation_id = log_request_start(
        method=request.method,
        path=request.url.path,
        user_id=getattr(request.state, "user_id", None),
    )

    # Add correlation ID to request state
    request.state.correlation_id = correlation_id

    # Process request
    response = call_next(request)

    # Log request completion
    duration_ms = (time.time() - start_time) * 1000
    log_request_end(
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
        user_id=getattr(request.state, "user_id", None),
    )

    # Add correlation ID to response headers
    response.headers["X-Correlation-ID"] = correlation_id

    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler with structured logging."""
    correlation_id = getattr(request.state, "correlation_id", None)

    logger.error(
        "Unhandled exception",
        correlation_id=correlation_id,
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )

    # Record error metrics
    metrics_collector.record_error(type(exc).__name__)

    if settings.DEBUG:
        return JSONResponse(
            status_code=500,
            content={
                "detail": str(exc),
                "type": type(exc).__name__,
                "path": request.url.path,
                "correlation_id": correlation_id,
            },
        )
    else:
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "correlation_id": correlation_id,
            },
        )


# HTTP exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP exception handler with structured logging."""
    correlation_id = getattr(request.state, "correlation_id", None)

    logger.warning(
        "HTTP exception",
        correlation_id=correlation_id,
        path=request.url.path,
        method=request.method,
        status_code=exc.status_code,
        detail=exc.detail,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "correlation_id": correlation_id},
    )


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "ACP Ingest Service",
        "version": "1.0.0",
        "status": "running",
        "docs_url": "/docs" if settings.DEBUG else None,
        "environment": settings.ENVIRONMENT,
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check database connectivity
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        # Check Redis connectivity
        import redis

        redis_client = redis.from_url(settings.REDIS_URL)
        redis_client.ping()

        # Check ChromaDB connectivity
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://{settings.CHROMA_HOST}:{settings.CHROMA_PORT}/api/v1/heartbeat"
            )
            response.raise_for_status()

        return {
            "status": "healthy",
            "timestamp": time.time(),
            "services": {
                "database": "healthy",
                "redis": "healthy",
                "chroma": "healthy",
            },
        }
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e), "timestamp": time.time()},
        )


# Metrics endpoint
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return get_metrics_endpoint()()


# Authentication endpoints
@app.get("/auth/login")
async def login():
    """Initiate OAuth2 login flow."""
    try:
        from .auth.oauth2 import OAuth2Service

        oauth2_service = OAuth2Service(security_config)

        # Generate state for CSRF protection
        import secrets

        state = secrets.token_urlsafe(32)

        # Store state in session (in production, use Redis or database)
        # For now, we'll return the authorization URL
        auth_url = await oauth2_service.get_authorization_url(state)

        return {"authorization_url": auth_url, "state": state}
    except Exception as e:
        logger.error("Login initiation failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to initiate login")


@app.post("/auth/callback")
async def auth_callback(code: str, state: str):
    """Handle OAuth2 callback."""
    try:
        from .auth.oauth2 import OAuth2Service

        oauth2_service = OAuth2Service(security_config)

        # Exchange code for token
        token_response = await oauth2_service.exchange_code_for_token(code, state)

        return token_response
    except Exception as e:
        logger.error("Auth callback failed", error=str(e))
        raise HTTPException(status_code=400, detail="Authentication failed")


# Protected endpoints
@app.get("/api/v1/profile")
async def get_profile(
    current_user: dict = Depends(auth_manager.get_current_active_user),
):
    """Get current user profile."""
    return {
        "user_id": current_user["sub"],
        "email": current_user["email"],
        "name": current_user.get("name", ""),
    }


# Include API routers
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(ingest.router, prefix="/api/v1", tags=["ingest"])
app.include_router(search.router, prefix="/api/v1", tags=["search"])


if __name__ == "__main__":
    # Run with uvicorn
    uvicorn.run(
        "app.main_enhanced:app",
        host=settings.host,
        port=settings.port,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True,
    )
