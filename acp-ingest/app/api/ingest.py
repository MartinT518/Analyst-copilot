"""Ingest API endpoints."""

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.config import get_settings
from app.database import get_db
from app.models import IngestJob, KnowledgeChunk
from app.schemas import IngestJobCreate, IngestJobResponse, JobStatusResponse, PasteRequest
from app.services.auth_service import get_current_user
from app.services.ingest_service import IngestService
from app.utils.file_utils import detect_file_type, get_file_info, save_upload_file
from app.utils.logging_config import get_audit_logger, get_logger, get_performance_logger
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

logger = get_logger(__name__)
audit_logger = get_audit_logger()
performance_logger = get_performance_logger()

router = APIRouter(prefix="/ingest", tags=["ingest"])
settings = get_settings()


class UploadResponse(BaseModel):
    """Response model for file upload."""

    job_id: str
    status: str
    message: str
    file_info: Dict[str, Any]


class PasteResponse(BaseModel):
    """Response model for text paste."""

    job_id: str
    status: str
    message: str
    text_length: int


class JobListResponse(BaseModel):
    """Response model for job listing."""

    jobs: List[IngestJobResponse]
    total: int
    skip: int
    limit: int


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    origin: str = Form(..., description="Customer or source identifier"),
    sensitivity: str = Form(..., description="Data sensitivity level"),
    source_type: Optional[str] = Form(
        None, description="Source type (auto-detected if not provided)"
    ),
    metadata: str = Form("{}", description="Additional metadata as JSON string"),
    db: Session = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """
    Upload a file for ingestion.

    Args:
        file: File to upload
        origin: Customer or source identifier
        sensitivity: Data sensitivity level
        source_type: Source type (optional, auto-detected)
        metadata: Additional metadata as JSON string
        db: Database session
        current_user: Current authenticated user

    Returns:
        UploadResponse: Upload result with job information
    """
    start_time = datetime.utcnow()

    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        if file.size and file.size > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE} bytes",
            )

        # Parse metadata
        try:
            metadata_dict = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON in metadata")

        # Save uploaded file
        file_path = await save_upload_file(file, settings.UPLOAD_DIR)
        file_info = get_file_info(file_path)

        # Detect source type if not provided
        if not source_type:
            source_type = detect_file_type(file.filename, file.content_type)

        # Create ingest job
        job_data = IngestJobCreate(
            origin=origin,
            source_type=source_type,
            sensitivity=sensitivity,
            file_path=file_path,
            metadata={
                **metadata_dict,
                "original_filename": file.filename,
                "file_size": file_info.get("size", 0),
                "content_type": file.content_type,
                "upload_timestamp": datetime.utcnow().isoformat(),
            },
        )

        # Create job in database
        job = IngestJob(
            id=str(uuid.uuid4()),
            origin=job_data.origin,
            source_type=job_data.source_type,
            sensitivity=job_data.sensitivity,
            file_path=job_data.file_path,
            metadata=job_data.metadata,
            status="pending",
            created_at=datetime.utcnow(),
            user_id=current_user.get("user_id") if current_user else None,
        )

        db.add(job)
        db.commit()
        db.refresh(job)

        # Queue background processing
        ingest_service = IngestService()
        background_tasks.add_task(ingest_service.process_job, job.id)

        # Log audit event
        audit_logger.log_event(
            action="file_upload",
            user_id=current_user.get("user_id") if current_user else "anonymous",
            resource_type="ingest_job",
            resource_id=str(job.id),
            details={
                "filename": file.filename,
                "source_type": source_type,
                "origin": origin,
                "sensitivity": sensitivity,
                "file_size": file_info.get("size", 0),
            },
        )

        # Log performance
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        performance_logger.log_operation(
            operation="file_upload",
            duration_ms=duration_ms,
            success=True,
            details={"file_size": file_info.get("size", 0), "source_type": source_type},
        )

        logger.info(
            "File uploaded successfully",
            job_id=str(job.id),
            filename=file.filename,
            source_type=source_type,
            origin=origin,
        )

        return UploadResponse(
            job_id=str(job.id),
            status=str(job.status),
            message="File uploaded successfully and queued for processing",
            file_info=file_info,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("File upload failed", error=str(e), filename=file.filename if file else None)

        # Log performance failure
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        performance_logger.log_operation(
            operation="file_upload",
            duration_ms=duration_ms,
            success=False,
            details={"error": str(e)},
        )

        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/paste", response_model=PasteResponse)
async def paste_text(
    request: PasteRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """
    Paste text content for ingestion.

    Args:
        request: Paste request with text and metadata
        background_tasks: Background tasks
        db: Database session
        current_user: Current authenticated user

    Returns:
        PasteResponse: Paste result with job information
    """
    start_time = datetime.utcnow()

    try:
        # Validate text length
        if len(request.text) > settings.MAX_TEXT_LENGTH:
            raise HTTPException(
                status_code=413,
                detail=f"Text too long. Maximum length: {settings.MAX_TEXT_LENGTH} characters",
            )

        if len(request.text.strip()) == 0:
            raise HTTPException(status_code=400, detail="Empty text content")

        # Create temporary file for text content
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, dir=settings.UPLOAD_DIR
        ) as f:
            f.write(request.text)
            text_file_path = f.name

        # Create ingest job
        job = IngestJob(
            id=str(uuid.uuid4()),
            origin=request.origin,
            source_type="paste",
            sensitivity=request.sensitivity,
            file_path=text_file_path,
            metadata={
                **request.metadata,
                "text_length": len(request.text),
                "ticket_id": request.ticket_id,
                "paste_timestamp": datetime.utcnow().isoformat(),
            },
            status="pending",
            created_at=datetime.utcnow(),
            user_id=current_user.get("user_id") if current_user else None,
        )

        db.add(job)
        db.commit()
        db.refresh(job)

        # Queue background processing
        ingest_service = IngestService()
        background_tasks.add_task(ingest_service.process_job, job.id)

        # Log audit event
        audit_logger.log_event(
            action="text_paste",
            user_id=current_user.get("user_id") if current_user else "anonymous",
            resource_type="ingest_job",
            resource_id=str(job.id),
            details={
                "text_length": len(request.text),
                "origin": request.origin,
                "sensitivity": request.sensitivity,
                "ticket_id": request.ticket_id,
            },
        )

        # Log performance
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        performance_logger.log_operation(
            operation="text_paste",
            duration_ms=duration_ms,
            success=True,
            details={"text_length": len(request.text)},
        )

        logger.info(
            "Text pasted successfully",
            job_id=str(job.id),
            text_length=len(request.text),
            origin=request.origin,
        )

        return PasteResponse(
            job_id=str(job.id),
            status=str(job.status),
            message="Text pasted successfully and queued for processing",
            text_length=len(request.text),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Text paste failed", error=str(e))

        # Log performance failure
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        performance_logger.log_operation(
            operation="text_paste",
            duration_ms=duration_ms,
            success=False,
            details={"error": str(e)},
        )

        raise HTTPException(status_code=500, detail=f"Paste failed: {str(e)}")


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """
    Get status of an ingest job.

    Args:
        job_id: Job ID to check
        db: Database session
        current_user: Current authenticated user

    Returns:
        JobStatusResponse: Job status information
    """
    try:
        # Get job from database
        job = db.query(IngestJob).filter(IngestJob.id == job_id).first()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Check authorization (users can only see their own jobs unless admin)
        if current_user and not current_user.get("is_admin", False):
            if job.user_id != current_user.get("user_id"):
                raise HTTPException(status_code=403, detail="Access denied")

        # Get chunk count
        chunk_count = db.query(KnowledgeChunk).filter(KnowledgeChunk.job_id == job_id).count()

        logger.debug("Job status retrieved", job_id=job_id, status=job.status)

        return JobStatusResponse(
            id=job.id,
            status=str(job.status),
            origin=job.origin,
            source_type=job.source_type,
            sensitivity=job.sensitivity,
            chunks_created=chunk_count,
            created_at=job.created_at,
            updated_at=job.updated_at,
            completed_at=job.completed_at,
            error_message=job.error_message,
            metadata=job.metadata,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get job status", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    skip: int = 0,
    limit: int = 10,
    status: Optional[str] = None,
    origin: Optional[str] = None,
    source_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """
    List ingest jobs with optional filtering.

    Args:
        skip: Number of jobs to skip
        limit: Maximum number of jobs to return
        status: Filter by status
        origin: Filter by origin
        source_type: Filter by source type
        db: Database session
        current_user: Current authenticated user

    Returns:
        JobListResponse: List of jobs with pagination info
    """
    try:
        # Build query
        query = db.query(IngestJob)

        # Apply user filtering (non-admin users see only their jobs)
        if current_user and not current_user.get("is_admin", False):
            query = query.filter(IngestJob.user_id == current_user.get("user_id"))

        # Apply filters
        if status:
            query = query.filter(IngestJob.status == status)
        if origin:
            query = query.filter(IngestJob.origin == origin)
        if source_type:
            query = query.filter(IngestJob.source_type == source_type)

        # Get total count
        total = query.count()

        # Apply pagination and ordering
        jobs = query.order_by(IngestJob.created_at.desc()).offset(skip).limit(limit).all()

        # Convert to response models
        job_responses = []
        for job in jobs:
            chunk_count = db.query(KnowledgeChunk).filter(KnowledgeChunk.job_id == job.id).count()

            job_responses.append(
                IngestJobResponse(
                    id=job.id,
                    status=str(job.status),
                    origin=job.origin,
                    source_type=job.source_type,
                    sensitivity=job.sensitivity,
                    chunks_created=chunk_count,
                    created_at=job.created_at,
                    updated_at=job.updated_at,
                    completed_at=job.completed_at,
                    error_message=job.error_message,
                    metadata=job.metadata,
                )
            )

        logger.debug("Jobs listed", total=total, returned=len(job_responses))

        return JobListResponse(jobs=job_responses, total=total, skip=skip, limit=limit)

    except Exception as e:
        logger.error("Failed to list jobs", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {str(e)}")


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """
    Delete an ingest job and its associated data.

    Args:
        job_id: Job ID to delete
        db: Database session
        current_user: Current authenticated user

    Returns:
        JSONResponse: Deletion result
    """
    try:
        # Get job from database
        job = db.query(IngestJob).filter(IngestJob.id == job_id).first()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Check authorization
        if current_user and not current_user.get("is_admin", False):
            if job.user_id != current_user.get("user_id"):
                raise HTTPException(status_code=403, detail="Access denied")

        # Delete associated chunks
        db.query(KnowledgeChunk).filter(KnowledgeChunk.job_id == job_id).delete()

        # Delete job
        db.delete(job)
        db.commit()

        # Clean up file if it exists
        if job.file_path and os.path.exists(job.file_path):
            try:
                os.remove(job.file_path)
            except Exception as e:
                logger.warning("Failed to delete file", file_path=job.file_path, error=str(e))

        # Log audit event
        audit_logger.log_event(
            action="job_delete",
            user_id=current_user.get("user_id") if current_user else "anonymous",
            resource_type="ingest_job",
            resource_id=job_id,
            details={"origin": job.origin, "source_type": job.source_type},
        )

        logger.info("Job deleted successfully", job_id=job_id)

        return JSONResponse(
            status_code=200,
            content={"message": "Job deleted successfully", "job_id": job_id},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete job", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete job: {str(e)}")


@router.post("/jobs/{job_id}/retry")
async def retry_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """
    Retry a failed ingest job.

    Args:
        job_id: Job ID to retry
        background_tasks: Background tasks
        db: Database session
        current_user: Current authenticated user

    Returns:
        JSONResponse: Retry result
    """
    try:
        # Get job from database
        job = db.query(IngestJob).filter(IngestJob.id == job_id).first()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Check authorization
        if current_user and not current_user.get("is_admin", False):
            if job.user_id != current_user.get("user_id"):
                raise HTTPException(status_code=403, detail="Access denied")

        # Check if job can be retried
        if job.status not in ["failed", "completed"]:
            raise HTTPException(status_code=400, detail="Job cannot be retried in current status")

        # Reset job status
        job.status = "pending"
        job.error_message = None
        job.updated_at = datetime.utcnow()
        job.completed_at = None

        db.commit()

        # Queue background processing
        ingest_service = IngestService()
        background_tasks.add_task(ingest_service.process_job, job.id)

        # Log audit event
        audit_logger.log_event(
            action="job_retry",
            user_id=current_user.get("user_id") if current_user else "anonymous",
            resource_type="ingest_job",
            resource_id=job_id,
            details={"origin": job.origin, "source_type": job.source_type},
        )

        logger.info("Job retry initiated", job_id=job_id)

        return JSONResponse(
            status_code=200,
            content={
                "message": "Job retry initiated",
                "job_id": job_id,
                "status": job.status,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retry job", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to retry job: {str(e)}")


@router.get("/stats")
async def get_ingest_stats(
    db: Session = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """
    Get ingestion statistics.

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        Dict[str, Any]: Ingestion statistics
    """
    try:
        # Build base query
        query = db.query(IngestJob)

        # Apply user filtering for non-admin users
        if current_user and not current_user.get("is_admin", False):
            query = query.filter(IngestJob.user_id == current_user.get("user_id"))

        # Get job counts by status
        total_jobs = query.count()
        pending_jobs = query.filter(IngestJob.status == "pending").count()
        processing_jobs = query.filter(IngestJob.status == "processing").count()
        completed_jobs = query.filter(IngestJob.status == "completed").count()
        failed_jobs = query.filter(IngestJob.status == "failed").count()

        # Get job counts by source type
        source_type_stats = {}
        for source_type in [
            "jira_csv",
            "confluence_html",
            "confluence_xml",
            "pdf",
            "markdown",
            "paste",
        ]:
            count = query.filter(IngestJob.source_type == source_type).count()
            if count > 0:
                source_type_stats[source_type] = count

        # Get total chunks created
        chunk_query = db.query(KnowledgeChunk)
        if current_user and not current_user.get("is_admin", False):
            # Filter chunks by user's jobs
            user_job_ids = [job.id for job in query.all()]
            chunk_query = chunk_query.filter(KnowledgeChunk.job_id.in_(user_job_ids))

        total_chunks = chunk_query.count()

        stats = {
            "total_jobs": total_jobs,
            "job_status": {
                "pending": pending_jobs,
                "processing": processing_jobs,
                "completed": completed_jobs,
                "failed": failed_jobs,
            },
            "source_types": source_type_stats,
            "total_chunks": total_chunks,
            "success_rate": ((completed_jobs / total_jobs * 100) if total_jobs > 0 else 0),
        }

        logger.debug("Ingest stats retrieved", stats=stats)

        return stats

    except Exception as e:
        logger.error("Failed to get ingest stats", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
