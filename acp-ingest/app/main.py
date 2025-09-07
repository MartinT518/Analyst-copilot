"""Main FastAPI application for ACP Ingest service."""

import os
from contextlib import asynccontextmanager
from typing import Any, Dict

import uvicorn
from app.api import health, ingest, search
from app.config import get_settings
from app.database import Base, engine
from app.utils.file_utils import ensure_directory
from app.utils.logging_config import LoggingMiddleware, get_logger, setup_logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

# Setup logging
settings = get_settings()
setup_logging(
    log_level=settings.LOG_LEVEL,
    log_format=settings.LOG_FORMAT,
    log_file=settings.LOG_FILE,
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting ACP Ingest service")

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

    # Initialize services
    try:
        from app.services.vector_service import VectorService

        vector_service = VectorService()
        await vector_service.initialize()
        logger.info("Vector service initialized")
    except Exception as e:
        logger.warning("Vector service initialization failed", error=str(e))

    try:
        from app.utils.pii_detector import PIIDetector

        pii_detector = PIIDetector()
        await pii_detector.initialize()
        logger.info("PII detector initialized")
    except Exception as e:
        logger.warning("PII detector initialization failed", error=str(e))

    logger.info("ACP Ingest service startup completed")

    yield

    # Shutdown
    logger.info("Shutting down ACP Ingest service")


# Create FastAPI application
app = FastAPI(
    title="ACP Ingest Service",
    description="On-premises AI-powered analysis system for processing exported data",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
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
if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"],  # Configure appropriately for production
    )

# Add logging middleware
logging_middleware = LoggingMiddleware()
app.middleware("http")(logging_middleware)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )

    if settings.DEBUG:
        return JSONResponse(
            status_code=500,
            content={
                "detail": str(exc),
                "type": type(exc).__name__,
                "path": request.url.path,
            },
        )
    else:
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )


# HTTP exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP exception handler."""
    logger.warning(
        "HTTP exception",
        path=request.url.path,
        method=request.method,
        status_code=exc.status_code,
        detail=exc.detail,
    )

    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


# Include API routers
app.include_router(health.router)
app.include_router(ingest.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "ACP Ingest Service",
        "version": "1.0.0",
        "status": "running",
        "docs_url": "/docs" if settings.DEBUG else None,
    }


# API info endpoint
@app.get("/api/v1/info")
async def api_info():
    """API information endpoint."""
    return {
        "api_version": "v1",
        "service": "ACP Ingest Service",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "ingest": "/api/v1/ingest",
            "search": "/api/v1/search",
        },
        "supported_formats": [
            "jira_csv",
            "confluence_html",
            "confluence_xml",
            "pdf",
            "markdown",
            "paste",
        ],
    }


# Configuration endpoint (debug only)
@app.get("/api/v1/config")
async def get_config():
    """Get service configuration (debug only)."""
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not found")

    # Return safe configuration (no secrets)
    safe_config = {
        "debug": settings.DEBUG,
        "log_level": settings.LOG_LEVEL,
        "max_file_size": settings.MAX_FILE_SIZE,
        "upload_dir": settings.UPLOAD_DIR,
        "database_url": (
            settings.DATABASE_URL.split("@")[-1]
            if "@" in settings.DATABASE_URL
            else "***"
        ),
        "redis_url": (
            settings.REDIS_URL.split("@")[-1] if "@" in settings.REDIS_URL else "***"
        ),
        "chroma_host": settings.CHROMA_HOST,
        "chroma_port": settings.CHROMA_PORT,
        "llm_endpoint": settings.LLM_ENDPOINT,
        "embedding_endpoint": settings.EMBEDDING_ENDPOINT,
    }

    return safe_config


if __name__ == "__main__":
    # Run with uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True,
    )
