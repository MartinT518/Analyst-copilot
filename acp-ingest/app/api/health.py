"""Health check API endpoints."""

import asyncio
from datetime import datetime
from typing import Any, Dict

from app.config import get_settings
from app.database import get_db
from app.utils.logging_config import get_logger
from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = get_logger(__name__)
router = APIRouter(tags=["health"])
settings = get_settings()


async def check_database() -> Dict[str, Any]:
    """Check database connectivity."""
    try:
        db = next(get_db())
        result = db.execute(text("SELECT 1")).fetchone()
        db.close()

        return {
            "status": "healthy",
            "response_time_ms": 0,  # Could add timing if needed
            "details": "Database connection successful",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "details": "Database connection failed",
        }


async def check_redis() -> Dict[str, Any]:
    """Check Redis connectivity."""
    try:
        import redis

        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        r.close()

        return {"status": "healthy", "details": "Redis connection successful"}
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "details": "Redis connection failed",
        }


async def check_chroma() -> Dict[str, Any]:
    """Check Chroma vector database connectivity."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"http://{settings.CHROMA_HOST}:{settings.CHROMA_PORT}/api/v1/heartbeat"
            )

            if response.status_code == 200:
                return {"status": "healthy", "details": "Chroma connection successful"}
            else:
                return {
                    "status": "unhealthy",
                    "error": f"HTTP {response.status_code}",
                    "details": "Chroma returned non-200 status",
                }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "details": "Chroma connection failed",
        }


async def check_llm_endpoint() -> Dict[str, Any]:
    """Check LLM endpoint connectivity."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try to get models list as a health check
            headers = {}
            if settings.OPENAI_API_KEY:
                headers["Authorization"] = f"Bearer {settings.OPENAI_API_KEY}"

            response = await client.get(
                f"{settings.LLM_ENDPOINT}/v1/models", headers=headers
            )

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


async def check_embedding_endpoint() -> Dict[str, Any]:
    """Check embedding endpoint connectivity."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try to get models list as a health check
            headers = {}
            if settings.OPENAI_API_KEY:
                headers["Authorization"] = f"Bearer {settings.OPENAI_API_KEY}"

            response = await client.get(
                f"{settings.EMBEDDING_ENDPOINT}/models", headers=headers
            )

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


async def check_disk_space() -> Dict[str, Any]:
    """Check available disk space."""
    try:
        import shutil

        # Check upload directory space
        total, used, free = shutil.disk_usage(settings.UPLOAD_DIR)

        # Convert to GB
        total_gb = total / (1024**3)
        free_gb = free / (1024**3)
        used_gb = used / (1024**3)

        # Consider unhealthy if less than 1GB free
        status = "healthy" if free_gb > 1.0 else "unhealthy"

        return {
            "status": status,
            "details": f"Free: {free_gb:.2f}GB, Used: {used_gb:.2f}GB, Total: {total_gb:.2f}GB",
            "free_gb": round(free_gb, 2),
            "used_gb": round(used_gb, 2),
            "total_gb": round(total_gb, 2),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "details": "Disk space check failed",
        }


@router.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint.

    Returns:
        Dict[str, Any]: Health status of all services
    """
    try:
        # Run all health checks concurrently
        checks = await asyncio.gather(
            check_database(),
            check_redis(),
            check_chroma(),
            check_llm_endpoint(),
            check_embedding_endpoint(),
            check_disk_space(),
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
            "chroma": (
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
            "disk_space": (
                checks[5]
                if not isinstance(checks[5], Exception)
                else {"status": "unhealthy", "error": str(checks[5])}
            ),
        }

        # Determine overall status
        all_healthy = all(
            service.get("status") == "healthy" for service in services.values()
        )
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
    """
    Kubernetes liveness probe endpoint.

    Returns:
        Dict[str, str]: Simple liveness status
    """
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}


@router.get("/health/ready")
async def readiness_probe():
    """
    Kubernetes readiness probe endpoint.

    Returns:
        Dict[str, Any]: Readiness status with critical services
    """
    try:
        # Check only critical services for readiness
        db_check = await check_database()
        redis_check = await check_redis()

        critical_services = {"database": db_check, "redis": redis_check}

        # Ready if critical services are healthy
        ready = all(
            service.get("status") == "healthy" for service in critical_services.values()
        )

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
    """
    Kubernetes startup probe endpoint.

    Returns:
        Dict[str, Any]: Startup status
    """
    try:
        # Check if application has started successfully
        # This could include checking if migrations are complete, etc.

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
    """
    Get application metrics for monitoring.

    Returns:
        Dict[str, Any]: Application metrics
    """
    try:
        from app.models import IngestJob, KnowledgeChunk

        # Get database session
        db = next(get_db())

        try:
            # Get job metrics
            total_jobs = db.query(IngestJob).count()
            pending_jobs = (
                db.query(IngestJob).filter(IngestJob.status == "pending").count()
            )
            processing_jobs = (
                db.query(IngestJob).filter(IngestJob.status == "processing").count()
            )
            completed_jobs = (
                db.query(IngestJob).filter(IngestJob.status == "completed").count()
            )
            failed_jobs = (
                db.query(IngestJob).filter(IngestJob.status == "failed").count()
            )

            # Get chunk metrics
            total_chunks = db.query(KnowledgeChunk).count()

            # Get disk usage
            disk_check = await check_disk_space()

            metrics = {
                "timestamp": datetime.utcnow().isoformat(),
                "jobs": {
                    "total": total_jobs,
                    "pending": pending_jobs,
                    "processing": processing_jobs,
                    "completed": completed_jobs,
                    "failed": failed_jobs,
                    "success_rate": (
                        (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0
                    ),
                },
                "chunks": {"total": total_chunks},
                "disk": {
                    "free_gb": disk_check.get("free_gb", 0),
                    "used_gb": disk_check.get("used_gb", 0),
                    "total_gb": disk_check.get("total_gb", 0),
                },
            }

            return metrics

        finally:
            db.close()

    except Exception as e:
        logger.error("Metrics collection error", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to collect metrics: {str(e)}"
        )


@router.get("/version")
async def get_version():
    """
    Get application version information.

    Returns:
        Dict[str, str]: Version information
    """
    return {
        "version": "1.0.0",
        "build_date": "2024-01-01",
        "git_commit": "unknown",
        "python_version": "3.11",
        "api_version": "v1",
    }
