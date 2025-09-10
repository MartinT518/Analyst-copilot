"""Main FastAPI application for ACP Code Analyzer service."""

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="ACP Code Analyzer",
    description="AI-powered code analysis and understanding service",
    version="1.0.0",
    debug=settings.debug,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "acp-code-analyzer"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "ACP Code Analyzer Service"}


def main():
    """Main entry point for the application."""
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,  # nosec B104 - configurable via settings
        port=settings.api_port,
        reload=settings.debug,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()
