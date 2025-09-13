"""Dead letter queue implementation for failed jobs."""

import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import JSON, Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = structlog.get_logger(__name__)

Base = declarative_base()


class JobStatus(Enum):
    """Job status enumeration."""

    PENDING = "pending"
    PROCESSING = "processing"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"
    RESOLVED = "resolved"


class DeadLetterJob(Base):
    """Dead letter queue job model."""

    __tablename__ = "dead_letter_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_type = Column(String, nullable=False)
    original_job_id = Column(String, nullable=True)
    payload = Column(JSON, nullable=False)
    error_message = Column(Text, nullable=True)
    error_type = Column(String, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    next_retry_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    job_metadata = Column(JSON, nullable=True)


class DeadLetterQueue:
    """Dead letter queue for failed jobs."""

    def __init__(self, database_url: str):
        """Initialize dead letter queue.

        Args:
            database_url: Database URL for storing failed jobs
        """
        self.database_url = database_url
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.logger = logger.bind(service="dead_letter_queue")

        # Create tables
        Base.metadata.create_all(bind=self.engine)

    def _get_session(self):
        """Get database session."""
        return self.SessionLocal()

    async def add_failed_job(
        self,
        job_type: str,
        payload: Dict[str, Any],
        error_message: str,
        error_type: str,
        original_job_id: Optional[str] = None,
        max_retries: int = 3,
        job_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Add a failed job to the dead letter queue.

        Args:
            job_type: Type of job that failed
            payload: Original job payload
            error_message: Error message
            error_type: Type of error
            original_job_id: Original job ID if available
            max_retries: Maximum number of retries
            job_metadata: Optional job metadata

        Returns:
            Dead letter job ID
        """
        session = self._get_session()
        try:
            job = DeadLetterJob(
                job_type=job_type,
                original_job_id=original_job_id,
                payload=payload,
                error_message=error_message,
                error_type=error_type,
                max_retries=max_retries,
                job_metadata=job_metadata or {},
            )

            session.add(job)
            session.commit()

            self.logger.info(
                "Failed job added to dead letter queue",
                job_id=job.id,
                job_type=job_type,
                error_type=error_type,
            )

            return job.id

        except Exception as e:
            session.rollback()
            self.logger.error("Failed to add job to dead letter queue", error=str(e))
            raise
        finally:
            session.close()

    async def get_retryable_jobs(
        self, job_type: Optional[str] = None, limit: int = 100
    ) -> List[DeadLetterJob]:
        """Get jobs that are ready for retry.

        Args:
            job_type: Optional job type filter
            limit: Maximum number of jobs to return

        Returns:
            List of retryable jobs
        """
        session = self._get_session()
        try:
            query = session.query(DeadLetterJob).filter(
                DeadLetterJob.status.in_([JobStatus.PENDING, JobStatus.RETRYING]),
                DeadLetterJob.retry_count < DeadLetterJob.max_retries,
                DeadLetterJob.next_retry_at <= datetime.utcnow(),
            )

            if job_type:
                query = query.filter(DeadLetterJob.job_type == job_type)

            jobs = query.limit(limit).all()

            self.logger.info("Retrieved retryable jobs", count=len(jobs), job_type=job_type)

            return jobs

        except Exception as e:
            self.logger.error("Failed to get retryable jobs", error=str(e))
            raise
        finally:
            session.close()

    async def mark_job_processing(self, job_id: str) -> bool:
        """Mark a job as processing.

        Args:
            job_id: Job ID

        Returns:
            True if successful, False if job not found
        """
        session = self._get_session()
        try:
            job = session.query(DeadLetterJob).filter(DeadLetterJob.id == job_id).first()

            if not job:
                return False

            job.status = JobStatus.PROCESSING
            job.updated_at = datetime.utcnow()

            session.commit()

            self.logger.info("Job marked as processing", job_id=job_id)
            return True

        except Exception as e:
            session.rollback()
            self.logger.error("Failed to mark job as processing", job_id=job_id, error=str(e))
            raise
        finally:
            session.close()

    async def mark_job_resolved(self, job_id: str) -> bool:
        """Mark a job as resolved.

        Args:
            job_id: Job ID

        Returns:
            True if successful, False if job not found
        """
        session = self._get_session()
        try:
            job = session.query(DeadLetterJob).filter(DeadLetterJob.id == job_id).first()

            if not job:
                return False

            job.status = JobStatus.RESOLVED
            job.resolved_at = datetime.utcnow()
            job.updated_at = datetime.utcnow()

            session.commit()

            self.logger.info("Job marked as resolved", job_id=job_id)
            return True

        except Exception as e:
            session.rollback()
            self.logger.error("Failed to mark job as resolved", job_id=job_id, error=str(e))
            raise
        finally:
            session.close()

    async def increment_retry_count(
        self,
        job_id: str,
        error_message: Optional[str] = None,
        error_type: Optional[str] = None,
    ) -> bool:
        """Increment retry count for a job.

        Args:
            job_id: Job ID
            error_message: Optional new error message
            error_type: Optional new error type

        Returns:
            True if successful, False if job not found
        """
        session = self._get_session()
        try:
            job = session.query(DeadLetterJob).filter(DeadLetterJob.id == job_id).first()

            if not job:
                return False

            job.retry_count += 1
            job.updated_at = datetime.utcnow()

            if error_message:
                job.error_message = error_message
            if error_type:
                job.error_type = error_type

            # Check if max retries exceeded
            if job.retry_count >= job.max_retries:
                job.status = JobStatus.DEAD_LETTER
                self.logger.warning(
                    "Job moved to dead letter status",
                    job_id=job_id,
                    retry_count=job.retry_count,
                    max_retries=job.max_retries,
                )
            else:
                job.status = JobStatus.RETRYING
                # Set next retry time (exponential backoff)
                delay_minutes = 2**job.retry_count
                job.next_retry_at = datetime.utcnow() + timedelta(minutes=delay_minutes)

            session.commit()

            self.logger.info(
                "Job retry count incremented",
                job_id=job_id,
                retry_count=job.retry_count,
                max_retries=job.max_retries,
            )

            return True

        except Exception as e:
            session.rollback()
            self.logger.error("Failed to increment retry count", job_id=job_id, error=str(e))
            raise
        finally:
            session.close()

    async def get_dead_letter_jobs(
        self, job_type: Optional[str] = None, limit: int = 100
    ) -> List[DeadLetterJob]:
        """Get jobs in dead letter status.

        Args:
            job_type: Optional job type filter
            limit: Maximum number of jobs to return

        Returns:
            List of dead letter jobs
        """
        session = self._get_session()
        try:
            query = session.query(DeadLetterJob).filter(
                DeadLetterJob.status == JobStatus.DEAD_LETTER
            )

            if job_type:
                query = query.filter(DeadLetterJob.job_type == job_type)

            jobs = query.order_by(DeadLetterJob.created_at.desc()).limit(limit).all()

            self.logger.info("Retrieved dead letter jobs", count=len(jobs), job_type=job_type)

            return jobs

        except Exception as e:
            self.logger.error("Failed to get dead letter jobs", error=str(e))
            raise
        finally:
            session.close()

    async def get_job_stats(self) -> Dict[str, Any]:
        """Get dead letter queue statistics.

        Returns:
            Dictionary with queue statistics
        """
        session = self._get_session()
        try:
            total_jobs = session.query(DeadLetterJob).count()
            pending_jobs = (
                session.query(DeadLetterJob)
                .filter(DeadLetterJob.status == JobStatus.PENDING)
                .count()
            )
            retrying_jobs = (
                session.query(DeadLetterJob)
                .filter(DeadLetterJob.status == JobStatus.RETRYING)
                .count()
            )
            dead_letter_jobs = (
                session.query(DeadLetterJob)
                .filter(DeadLetterJob.status == JobStatus.DEAD_LETTER)
                .count()
            )
            resolved_jobs = (
                session.query(DeadLetterJob)
                .filter(DeadLetterJob.status == JobStatus.RESOLVED)
                .count()
            )

            stats = {
                "total_jobs": total_jobs,
                "pending_jobs": pending_jobs,
                "retrying_jobs": retrying_jobs,
                "dead_letter_jobs": dead_letter_jobs,
                "resolved_jobs": resolved_jobs,
            }

            self.logger.info("Retrieved dead letter queue stats", **stats)
            return stats

        except Exception as e:
            self.logger.error("Failed to get dead letter queue stats", error=str(e))
            raise
        finally:
            session.close()

    async def cleanup_resolved_jobs(self, older_than_days: int = 30) -> int:
        """Clean up resolved jobs older than specified days.

        Args:
            older_than_days: Number of days to keep resolved jobs

        Returns:
            Number of jobs cleaned up
        """
        session = self._get_session()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)

            deleted_count = (
                session.query(DeadLetterJob)
                .filter(
                    DeadLetterJob.status == JobStatus.RESOLVED,
                    DeadLetterJob.resolved_at < cutoff_date,
                )
                .delete()
            )

            session.commit()

            self.logger.info(
                "Cleaned up resolved jobs",
                deleted_count=deleted_count,
                older_than_days=older_than_days,
            )

            return deleted_count

        except Exception as e:
            session.rollback()
            self.logger.error("Failed to cleanup resolved jobs", error=str(e))
            raise
        finally:
            session.close()


def get_dead_letter_queue(database_url: str) -> DeadLetterQueue:
    """Get dead letter queue instance.

    Args:
        database_url: Database URL

    Returns:
        Dead letter queue instance
    """
    return DeadLetterQueue(database_url)
