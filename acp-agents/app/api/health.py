"""Health check API endpoints for ACP Agents service."""

import asyncio
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from ..config import get_settings
from ..database import get_db
from ..utils.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["health"])
settings = get_settings()


async def check_database() -> dict[str, Any]:
    """Check database connectivity."""
    try:
        db = next(get_db())
        db.execute(text("SELECT 1")).fetchone()
        db.close()

        return {
            "status": "healthy",
            "response_time_ms": 0,
            "details": "Database connection successful",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "details": "Database connection failed",
        }


async def check_redis() -> dict[str, Any]:
    """Check Redis connectivity."""
    try:
        import redis

        r = redis.from_url(settings.redis_url)
        r.ping()
        r.close()

        return {"status": "healthy", "details": "Redis connection successful"}
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "details": "Redis connection failed",
        }


async def check_ingest_service() -> dict[str, Any]:
    """Check ingest service connectivity."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ingest_service_url}/health")

            if response.status_code == 200:
                return {"status": "healthy", "details": "Ingest service accessible"}
            else:
                return {
                    "status": "unhealthy",
                    "error": f"HTTP {response.status_code}",
                    "details": "Ingest service returned non-200 status",
                }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "details": "Ingest service connection failed",
        }


async def check_llm_endpoint() -> dict[str, Any]:
    """Check LLM endpoint connectivity."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {}
            if settings.api_key:
                headers["Authorization"] = f"Bearer {settings.api_key}"

            response = await client.get(f"{settings.llm_endpoint}/models", headers=headers)

            if response.status_code == 200:
                return {"status": "healthy", "details": "LLM endpoint accessible"}
            else:
                return {
                    "status": "unhealthy",
                    "error": f"HTTP {response.status_code}",
                    "details": "LLM endpoint returned non-200 status",
                }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "details": "LLM endpoint connection failed",
        }


async def check_embedding_endpoint() -> dict[str, Any]:
    """Check embedding endpoint connectivity."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {}
            if settings.api_key:
                headers["Authorization"] = f"Bearer {settings.api_key}"

            response = await client.get(f"{settings.embedding_endpoint}/models", headers=headers)

            if response.status_code == 200:
                return {"status": "healthy", "details": "Embedding endpoint accessible"}
            else:
                return {
                    "status": "unhealthy",
                    "error": f"HTTP {response.status_code}",
                    "details": "Embedding endpoint returned non-200 status",
                }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "details": "Embedding endpoint connection failed",
        }


@router.get("/health")
async def health_check():
    """Comprehensive health check endpoint.

    Returns:
        Dict[str, Any]: Health status of all services
    """
    try:
        # Run all health checks concurrently
        checks = await asyncio.gather(
            check_database(),
            check_redis(),
            check_ingest_service(),
            check_llm_endpoint(),
            check_embedding_endpoint(),
            return_exceptions=True,
        )

        # Map results to service names
        services = {
            "database": (
                checks[0]
                if not isinstance(checks[0], Exception)
                else {"status": "unhealthy", "error": str(checks[0])}
            ),
            "redis": (
                checks[1]
                if not isinstance(checks[1], Exception)
                else {"status": "unhealthy", "error": str(checks[1])}
            ),
            "ingest_service": (
                checks[2]
                if not isinstance(checks[2], Exception)
                else {"status": "unhealthy", "error": str(checks[2])}
            ),
            "llm_endpoint": (
                checks[3]
                if not isinstance(checks[3], Exception)
                else {"status": "unhealthy", "error": str(checks[3])}
            ),
            "embedding_endpoint": (
                checks[4]
                if not isinstance(checks[4], Exception)
                else {"status": "unhealthy", "error": str(checks[4])}
            ),
        }

        # Determine overall status
        all_healthy = all(service.get("status") == "healthy" for service in services.values())
        overall_status = "healthy" if all_healthy else "unhealthy"

        response = {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "services": services,
        }

        # Log health check result
        if overall_status == "healthy":
            logger.debug("Health check passed", services=services)
        else:
            logger.warning("Health check failed", services=services)

        return response

    except Exception as e:
        logger.error("Health check error", error=str(e))
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "error": str(e),
            "services": {},
        }


@router.get("/health/live")
async def liveness_probe():
    """Kubernetes liveness probe endpoint.

    Returns:
        Dict[str, str]: Simple liveness status
    """
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}


@router.get("/health/ready")
async def readiness_probe():
    """Kubernetes readiness probe endpoint.

    Returns:
        Dict[str, Any]: Readiness status with critical services
    """
    try:
        # Check only critical services for readiness
        db_check = await check_database()
        redis_check = await check_redis()
        ingest_check = await check_ingest_service()

        critical_services = {
            "database": db_check,
            "redis": redis_check,
            "ingest_service": ingest_check,
        }

        # Ready if critical services are healthy
        ready = all(service.get("status") == "healthy" for service in critical_services.values())

        response = {
            "status": "ready" if ready else "not_ready",
            "timestamp": datetime.utcnow().isoformat(),
            "critical_services": critical_services,
        }

        if not ready:
            logger.warning("Readiness check failed", services=critical_services)

        return response

    except Exception as e:
        logger.error("Readiness check error", error=str(e))
        return {
            "status": "not_ready",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
        }


@router.get("/health/startup")
async def startup_probe():
    """Kubernetes startup probe endpoint.

    Returns:
        Dict[str, Any]: Startup status
    """
    try:
        # Check if application has started successfully
        db_check = await check_database()

        if db_check.get("status") == "healthy":
            return {
                "status": "started",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Application started successfully",
            }
        else:
            return {
                "status": "starting",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Application still starting",
                "database": db_check,
            }

    except Exception as e:
        logger.error("Startup check error", error=str(e))
        return {
            "status": "starting",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
        }


@router.get("/metrics")
async def get_metrics():
    """Get application metrics for monitoring.

    Returns:
        Dict[str, Any]: Application metrics
    """
    try:
        # Get workflow metrics (if available)
        # This would need to be implemented based on your workflow storage
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "workflows": {
                "total": 0,  # Would be populated from actual workflow storage
                "active": 0,
                "completed": 0,
                "failed": 0,
            },
            "agents": {
                "clarifier": {"status": "healthy"},
                "synthesizer": {"status": "healthy"},
                "taskmaster": {"status": "healthy"},
                "verifier": {"status": "healthy"},
            },
        }

        return metrics

    except Exception as e:
        logger.error("Metrics collection error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to collect metrics: {str(e)}")


@router.get("/version")
async def get_version():
    """Get application version information.

    Returns:
        Dict[str, str]: Version information
    """
    return {
        "version": "1.0.0",
        "build_date": "2024-01-01",
        "git_commit": "unknown",
        "python_version": "3.11",
        "api_version": "v1",
        "service": "acp-agents",
    }
