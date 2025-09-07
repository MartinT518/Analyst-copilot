"""Celery worker for background job processing."""

import os
import asyncio
from datetime import datetime
from typing import Dict, Any

from celery import Celery
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from app.config import get_settings
from app.models import IngestJob
from app.services.ingest_service import IngestService
from app.utils.logging_config import setup_logging, get_logger

# Setup logging
settings = get_settings()
setup_logging(
    log_level=settings.LOG_LEVEL,
    log_format=settings.LOG_FORMAT,
    log_file=settings.LOG_FILE,
)

logger = get_logger(__name__)

# Create Celery app
celery_app = Celery(
    "acp-ingest",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.worker"],
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    result_expires=3600,  # 1 hour
    task_routes={
        "app.worker.process_ingest_job": {"queue": "ingest"},
        "app.worker.cleanup_old_jobs": {"queue": "maintenance"},
    },
    beat_schedule={
        "cleanup-old-jobs": {
            "task": "app.worker.cleanup_old_jobs",
            "schedule": 3600.0,  # Run every hour
        },
        "health-check": {
            "task": "app.worker.health_check_task",
            "schedule": 300.0,  # Run every 5 minutes
        },
    },
)

# Database setup for worker
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session():
    """Get database session for worker tasks."""
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


@celery_app.task(bind=True, name="app.worker.process_ingest_job")
def process_ingest_job(self, job_id: str) -> Dict[str, Any]:
    """
    Process an ingest job in the background.

    Args:
        job_id: ID of the job to process

    Returns:
        Dict[str, Any]: Processing result
    """
    logger.info("Starting job processing", job_id=job_id, task_id=self.request.id)

    db = get_db_session()

    try:
        # Get job from database
        job = db.query(IngestJob).filter(IngestJob.id == job_id).first()

        if not job:
            logger.error("Job not found", job_id=job_id)
            return {"status": "error", "message": "Job not found"}

        # Update job status to processing
        job.status = "processing"
        job.updated_at = datetime.utcnow()
        db.commit()

        logger.info("Job status updated to processing", job_id=job_id)

        # Create ingest service and process job
        ingest_service = IngestService()

        # Run async processing in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                ingest_service.process_job_async(job_id, db)
            )
            logger.info("Job processing completed", job_id=job_id, result=result)
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error("Job processing failed", job_id=job_id, error=str(e))

        # Update job status to failed
        try:
            job = db.query(IngestJob).filter(IngestJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.updated_at = datetime.utcnow()
                job.completed_at = datetime.utcnow()
                db.commit()
        except Exception as db_error:
            logger.error(
                "Failed to update job status", job_id=job_id, error=str(db_error)
            )

        return {"status": "error", "message": str(e)}

    finally:
        db.close()


@celery_app.task(name="app.worker.cleanup_old_jobs")
def cleanup_old_jobs() -> Dict[str, Any]:
    """
    Clean up old completed and failed jobs.

    Returns:
        Dict[str, Any]: Cleanup result
    """
    logger.info("Starting job cleanup task")

    db = get_db_session()

    try:
        from datetime import timedelta

        # Delete jobs older than 30 days
        cutoff_date = datetime.utcnow() - timedelta(days=30)

        # Get old jobs
        old_jobs = (
            db.query(IngestJob)
            .filter(
                IngestJob.completed_at < cutoff_date,
                IngestJob.status.in_(["completed", "failed"]),
            )
            .all()
        )

        deleted_count = 0

        for job in old_jobs:
            try:
                # Delete associated chunks
                from app.models import KnowledgeChunk

                db.query(KnowledgeChunk).filter(
                    KnowledgeChunk.job_id == job.id
                ).delete()

                # Delete job file if it exists
                if job.file_path and os.path.exists(job.file_path):
                    try:
                        os.remove(job.file_path)
                    except Exception as e:
                        logger.warning(
                            "Failed to delete job file",
                            file_path=job.file_path,
                            error=str(e),
                        )

                # Delete job
                db.delete(job)
                deleted_count += 1

            except Exception as e:
                logger.error("Failed to delete job", job_id=job.id, error=str(e))
                continue

        db.commit()

        logger.info("Job cleanup completed", deleted_count=deleted_count)

        return {
            "status": "success",
            "deleted_jobs": deleted_count,
            "cutoff_date": cutoff_date.isoformat(),
        }

    except Exception as e:
        logger.error("Job cleanup failed", error=str(e))
        return {"status": "error", "message": str(e)}

    finally:
        db.close()


@celery_app.task(name="app.worker.health_check_task")
def health_check_task() -> Dict[str, Any]:
    """
    Periodic health check task.

    Returns:
        Dict[str, Any]: Health check result
    """
    logger.debug("Running periodic health check")

    try:
        # Check database connectivity
        db = get_db_session()
        try:
            db.execute("SELECT 1")
            db_status = "healthy"
        except Exception as e:
            db_status = f"unhealthy: {str(e)}"
        finally:
            db.close()

        # Check Redis connectivity
        try:
            import redis

            r = redis.from_url(settings.REDIS_URL)
            r.ping()
            r.close()
            redis_status = "healthy"
        except Exception as e:
            redis_status = f"unhealthy: {str(e)}"

        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "database": db_status,
            "redis": redis_status,
        }

        # Log warning if any service is unhealthy
        if "unhealthy" in str(result):
            logger.warning("Health check detected issues", result=result)
        else:
            logger.debug("Health check passed", result=result)

        return result

    except Exception as e:
        logger.error("Health check task failed", error=str(e))
        return {"status": "error", "message": str(e)}


@celery_app.task(name="app.worker.reprocess_failed_jobs")
def reprocess_failed_jobs(max_retries: int = 3) -> Dict[str, Any]:
    """
    Reprocess failed jobs that might be recoverable.

    Args:
        max_retries: Maximum number of retries for a job

    Returns:
        Dict[str, Any]: Reprocessing result
    """
    logger.info("Starting failed job reprocessing", max_retries=max_retries)

    db = get_db_session()

    try:
        from datetime import timedelta

        # Get failed jobs from the last 24 hours that haven't exceeded max retries
        cutoff_date = datetime.utcnow() - timedelta(hours=24)

        failed_jobs = (
            db.query(IngestJob)
            .filter(
                IngestJob.status == "failed",
                IngestJob.updated_at > cutoff_date,
                IngestJob.retry_count < max_retries,
            )
            .all()
        )

        reprocessed_count = 0

        for job in failed_jobs:
            try:
                # Check if the failure might be recoverable
                if job.error_message and any(
                    keyword in job.error_message.lower()
                    for keyword in ["timeout", "connection", "temporary", "network"]
                ):
                    # Reset job for reprocessing
                    job.status = "pending"
                    job.error_message = None
                    job.retry_count = (job.retry_count or 0) + 1
                    job.updated_at = datetime.utcnow()

                    # Queue for processing
                    process_ingest_job.delay(job.id)
                    reprocessed_count += 1

                    logger.info(
                        "Job queued for reprocessing",
                        job_id=job.id,
                        retry_count=job.retry_count,
                    )

            except Exception as e:
                logger.error("Failed to reprocess job", job_id=job.id, error=str(e))
                continue

        db.commit()

        logger.info(
            "Failed job reprocessing completed", reprocessed_count=reprocessed_count
        )

        return {
            "status": "success",
            "reprocessed_jobs": reprocessed_count,
            "total_failed_jobs": len(failed_jobs),
        }

    except Exception as e:
        logger.error("Failed job reprocessing failed", error=str(e))
        return {"status": "error", "message": str(e)}

    finally:
        db.close()


@celery_app.task(name="app.worker.update_job_metrics")
def update_job_metrics() -> Dict[str, Any]:
    """
    Update job processing metrics.

    Returns:
        Dict[str, Any]: Metrics update result
    """
    logger.debug("Updating job metrics")

    db = get_db_session()

    try:
        # Get job statistics
        total_jobs = db.query(IngestJob).count()
        pending_jobs = db.query(IngestJob).filter(IngestJob.status == "pending").count()
        processing_jobs = (
            db.query(IngestJob).filter(IngestJob.status == "processing").count()
        )
        completed_jobs = (
            db.query(IngestJob).filter(IngestJob.status == "completed").count()
        )
        failed_jobs = db.query(IngestJob).filter(IngestJob.status == "failed").count()

        # Get chunk statistics
        from app.models import KnowledgeChunk

        total_chunks = db.query(KnowledgeChunk).count()

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
        }

        logger.debug("Job metrics updated", metrics=metrics)

        return metrics

    except Exception as e:
        logger.error("Failed to update job metrics", error=str(e))
        return {"status": "error", "message": str(e)}

    finally:
        db.close()


# Task routing and error handling
@celery_app.task(bind=True)
def debug_task(self):
    """Debug task for testing worker functionality."""
    logger.info("Debug task executed", task_id=self.request.id)
    return f"Request: {self.request!r}"


# Worker event handlers
@celery_app.task(bind=True)
def task_failure_handler(self, task_id, error, traceback):
    """Handle task failures."""
    logger.error("Task failed", task_id=task_id, error=str(error), traceback=traceback)


# Configure worker startup
def setup_worker():
    """Setup worker configuration."""
    logger.info("Setting up Celery worker")

    # Configure task routes
    celery_app.conf.task_routes = {
        "app.worker.process_ingest_job": {"queue": "ingest"},
        "app.worker.cleanup_old_jobs": {"queue": "maintenance"},
        "app.worker.health_check_task": {"queue": "monitoring"},
        "app.worker.reprocess_failed_jobs": {"queue": "maintenance"},
        "app.worker.update_job_metrics": {"queue": "monitoring"},
    }

    logger.info("Celery worker setup completed")


if __name__ == "__main__":
    setup_worker()
    celery_app.start()
