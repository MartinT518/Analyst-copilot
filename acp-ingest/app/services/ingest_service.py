"""Ingest service for processing and indexing documents."""

import os
import json
import asyncio
import logging
import tempfile
import shutil
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID
import aiofiles
import httpx
from sqlalchemy.orm import Session
from fastapi import UploadFile

from ..config import get_settings
from ..models import IngestJob, KnowledgeChunk, AuditLog
from ..schemas import IngestPasteRequest, JobResponse, SystemStatus, ProcessingStats
from ..parsers.jira_parser import JiraParser
from ..parsers.confluence_parser import ConfluenceParser
from ..parsers.pdf_parser import PDFParser
from ..parsers.markdown_parser import MarkdownParser
from ..parsers.code_parser import CodeParser
from ..parsers.db_schema_parser import DatabaseSchemaParser
from ..utils.pii_detector import PIIDetector
from ..utils.chunker import TextChunker
from ..utils.file_utils import detect_file_type, save_upload_file
from .vector_service import VectorService

logger = logging.getLogger(__name__)
settings = get_settings()


class IngestService:
    """Service for handling document ingestion and processing."""

    def __init__(self):
        self.settings = settings
        self.vector_service = VectorService()
        self.pii_detector = PIIDetector()
        self.chunker = TextChunker()

        # Initialize parsers
        self.parsers = {
            "jira_csv": JiraParser(),
            "confluence_html": ConfluenceParser(),
            "confluence_xml": ConfluenceParser(),
            "pdf": PDFParser(),
            "markdown": MarkdownParser(),
            "code": CodeParser(),
            "database_schema": DatabaseSchemaParser(),
        }

        # Ensure upload directory exists
        os.makedirs(settings.upload_dir, exist_ok=True)

    async def initialize(self):
        """Initialize the ingest service."""
        logger.info("Initializing ingest service")

        # Initialize vector service
        await self.vector_service.initialize()

        # Initialize PII detector
        await self.pii_detector.initialize()

        # Test embedding service connection
        if not await self.check_embedding_service():
            logger.warning("Embedding service is not available")

        logger.info("Ingest service initialized successfully")

    async def cleanup(self):
        """Cleanup resources."""
        logger.info("Cleaning up ingest service")
        await self.vector_service.cleanup()

    async def check_embedding_service(self) -> str:
        """
        Check if embedding service is available.

        Returns:
            str: Service status
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{settings.embedding_endpoint}/models")
                if response.status_code == 200:
                    return "healthy"
                else:
                    return "unhealthy"
        except Exception as e:
            logger.error(f"Embedding service check failed: {e}")
            return "unhealthy"

    async def create_upload_job(
        self,
        file: UploadFile,
        origin: str,
        sensitivity: str,
        source_type: Optional[str],
        metadata: str,
        uploader: str,
        db: Session,
    ) -> IngestJob:
        """
        Create a new upload job.

        Args:
            file: Uploaded file
            origin: Customer identifier
            sensitivity: Data sensitivity level
            source_type: Source type (auto-detected if None)
            metadata: Additional metadata as JSON string
            uploader: Username of uploader
            db: Database session

        Returns:
            IngestJob: Created job
        """
        try:
            # Parse metadata
            try:
                metadata_dict = json.loads(metadata) if metadata else {}
            except json.JSONDecodeError:
                metadata_dict = {}

            # Detect source type if not provided
            if not source_type:
                source_type = detect_file_type(file.filename, file.content_type)

            # Save uploaded file
            file_path = await save_upload_file(file, settings.upload_dir)

            # Create job record
            job = IngestJob(
                source_type=source_type,
                origin=origin,
                sensitivity=sensitivity,
                uploader=uploader,
                file_path=file_path,
                file_size=file.size,
                metadata=metadata_dict,
            )

            db.add(job)
            db.commit()
            db.refresh(job)

            # Create audit log
            audit_log = AuditLog(
                action="ingest_upload",
                user_id=uploader,
                resource_type="ingest_job",
                resource_id=str(job.id),
                details={
                    "filename": file.filename,
                    "file_size": file.size,
                    "source_type": source_type,
                    "origin": origin,
                    "sensitivity": sensitivity,
                },
            )
            db.add(audit_log)
            db.commit()

            logger.info(f"Created upload job {job.id} for file {file.filename}")
            return job

        except Exception as e:
            logger.error(f"Failed to create upload job: {e}")
            db.rollback()
            raise

    async def create_paste_job(
        self, request: IngestPasteRequest, uploader: str, db: Session
    ) -> IngestJob:
        """
        Create a new paste job.

        Args:
            request: Paste request data
            uploader: Username of uploader
            db: Database session

        Returns:
            IngestJob: Created job
        """
        try:
            # Create temporary file for pasted content
            temp_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", dir=settings.upload_dir, delete=False
            )
            temp_file.write(request.text)
            temp_file.close()

            # Create job record
            job = IngestJob(
                source_type="paste",
                origin=request.origin,
                sensitivity=request.sensitivity.value,
                uploader=uploader,
                file_path=temp_file.name,
                file_size=len(request.text.encode("utf-8")),
                metadata={"ticket_id": request.ticket_id, **request.metadata},
            )

            db.add(job)
            db.commit()
            db.refresh(job)

            # Create audit log
            audit_log = AuditLog(
                action="ingest_paste",
                user_id=uploader,
                resource_type="ingest_job",
                resource_id=str(job.id),
                details={
                    "text_length": len(request.text),
                    "origin": request.origin,
                    "sensitivity": request.sensitivity.value,
                    "ticket_id": request.ticket_id,
                },
            )
            db.add(audit_log)
            db.commit()

            logger.info(f"Created paste job {job.id}")
            return job

        except Exception as e:
            logger.error(f"Failed to create paste job: {e}")
            db.rollback()
            raise

    async def process_job(self, job_id: UUID, db: Session):
        """
        Process an ingestion job.

        Args:
            job_id: Job identifier
            db: Database session
        """
        job = db.query(IngestJob).filter(IngestJob.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        try:
            # Update job status
            job.status = "processing"
            job.started_at = datetime.utcnow()
            db.commit()

            logger.info(f"Processing job {job_id}")

            # Read file content
            async with aiofiles.open(job.file_path, "r", encoding="utf-8") as f:
                content = await f.read()

            # Parse content based on source type
            parser = self.parsers.get(job.source_type)
            if not parser:
                raise ValueError(
                    f"No parser available for source type: {job.source_type}"
                )

            parsed_content = await parser.parse(content, job.metadata)

            # Process each document/section
            chunks_created = 0
            for doc in parsed_content:
                chunks_created += await self._process_document(doc, job, db)

            # Update job status
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            job.chunks_created = chunks_created
            db.commit()

            logger.info(
                f"Job {job_id} completed successfully. Created {chunks_created} chunks."
            )

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")

            # Update job status
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()

            # Create audit log for failure
            audit_log = AuditLog(
                action="ingest_failed",
                user_id=job.uploader,
                resource_type="ingest_job",
                resource_id=str(job.id),
                details={"error": str(e)},
            )
            db.add(audit_log)
            db.commit()

    async def _process_document(
        self, document: Dict[str, Any], job: IngestJob, db: Session
    ) -> int:
        """
        Process a single document and create chunks.

        Args:
            document: Parsed document data
            job: Ingestion job
            db: Database session

        Returns:
            int: Number of chunks created
        """
        try:
            # Extract text content
            text_content = document.get("content", "")
            if not text_content.strip():
                return 0

            # Detect and redact PII
            if settings.pii_detection_enabled:
                text_content = await self.pii_detector.process_text(
                    text_content, mode=settings.pii_redaction_mode
                )

            # Create chunks
            chunks = await self.chunker.create_chunks(
                text=text_content,
                metadata={
                    "source_type": job.source_type,
                    "origin": job.origin,
                    "sensitivity": job.sensitivity,
                    "document_title": document.get("title", ""),
                    "document_id": document.get("id", ""),
                    "author": document.get("author", ""),
                    "created_at": document.get("created_at", ""),
                    **document.get("metadata", {}),
                    **job.metadata,
                },
            )

            # Generate embeddings and store chunks
            chunks_created = 0
            for chunk in chunks:
                try:
                    # Generate embedding
                    embedding = await self._generate_embedding(chunk["text"])

                    # Store in vector database
                    vector_id = await self.vector_service.add_vector(
                        embedding=embedding,
                        metadata=chunk["metadata"],
                        text=chunk["text"],
                    )

                    # Create knowledge chunk record
                    knowledge_chunk = KnowledgeChunk(
                        source_type=job.source_type,
                        source_location=job.file_path,
                        chunk_text=chunk["text"],
                        metadata=chunk["metadata"],
                        embedding_model=settings.embedding_model,
                        embedding_version="1.0",
                        vector_id=vector_id,
                        sensitive=(job.sensitivity in ["confidential", "restricted"]),
                        redacted=settings.pii_detection_enabled,
                    )

                    db.add(knowledge_chunk)
                    chunks_created += 1

                except Exception as e:
                    logger.error(f"Failed to process chunk: {e}")
                    continue

            db.commit()
            return chunks_created

        except Exception as e:
            logger.error(f"Failed to process document: {e}")
            db.rollback()
            return 0

    async def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            List[float]: Embedding vector
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{settings.embedding_endpoint}/embeddings",
                    json={"input": text, "model": settings.embedding_model},
                )
                response.raise_for_status()

                data = response.json()
                return data["data"][0]["embedding"]

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    async def get_job_status(self, job_id: UUID, db: Session) -> Optional[JobResponse]:
        """
        Get job status.

        Args:
            job_id: Job identifier
            db: Database session

        Returns:
            Optional[JobResponse]: Job data or None if not found
        """
        job = db.query(IngestJob).filter(IngestJob.id == job_id).first()
        if not job:
            return None

        return JobResponse.from_orm(job)

    async def list_jobs(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        origin: Optional[str] = None,
        db: Session = None,
    ) -> List[JobResponse]:
        """
        List ingestion jobs.

        Args:
            skip: Number of jobs to skip
            limit: Maximum number of jobs to return
            status: Filter by status
            origin: Filter by origin
            db: Database session

        Returns:
            List[JobResponse]: List of jobs
        """
        query = db.query(IngestJob)

        if status:
            query = query.filter(IngestJob.status == status)
        if origin:
            query = query.filter(IngestJob.origin == origin)

        jobs = query.offset(skip).limit(limit).all()
        return [JobResponse.from_orm(job) for job in jobs]

    async def estimate_processing_time(self, size: int) -> int:
        """
        Estimate processing time based on content size.

        Args:
            size: Content size in bytes

        Returns:
            int: Estimated processing time in seconds
        """
        # Simple estimation: ~1 second per 10KB
        base_time = max(5, size // 10240)
        return min(base_time, 300)  # Cap at 5 minutes

    async def get_processing_stats(self, db: Session) -> ProcessingStats:
        """
        Get processing statistics.

        Args:
            db: Database session

        Returns:
            ProcessingStats: Processing statistics
        """
        # Get job counts by status
        total_jobs = db.query(IngestJob).count()
        completed_jobs = (
            db.query(IngestJob).filter(IngestJob.status == "completed").count()
        )
        failed_jobs = db.query(IngestJob).filter(IngestJob.status == "failed").count()
        pending_jobs = (
            db.query(IngestJob)
            .filter(IngestJob.status.in_(["pending", "processing"]))
            .count()
        )

        # Get total chunks
        total_chunks = db.query(KnowledgeChunk).count()

        # Get jobs from last 24 hours
        yesterday = datetime.utcnow() - timedelta(days=1)
        last_24h_jobs = (
            db.query(IngestJob).filter(IngestJob.created_at >= yesterday).count()
        )

        # Calculate average processing time
        completed_jobs_with_time = (
            db.query(IngestJob)
            .filter(
                IngestJob.status == "completed",
                IngestJob.started_at.isnot(None),
                IngestJob.completed_at.isnot(None),
            )
            .all()
        )

        if completed_jobs_with_time:
            total_time = sum(
                [
                    (job.completed_at - job.started_at).total_seconds()
                    for job in completed_jobs_with_time
                ]
            )
            average_processing_time = total_time / len(completed_jobs_with_time)
        else:
            average_processing_time = 0.0

        return ProcessingStats(
            total_jobs=total_jobs,
            completed_jobs=completed_jobs,
            failed_jobs=failed_jobs,
            pending_jobs=pending_jobs,
            total_chunks=total_chunks,
            average_processing_time=average_processing_time,
            last_24h_jobs=last_24h_jobs,
        )

    async def get_system_status(self) -> SystemStatus:
        """
        Get detailed system status.

        Returns:
            SystemStatus: System status information
        """
        # Check database connection
        from ..database import check_db_connection

        database_connected = check_db_connection()

        # Check vector database
        vector_db_connected = await self.vector_service.health_check() == "healthy"

        # Check embedding service
        embedding_service_available = await self.check_embedding_service() == "healthy"

        # Check LLM service (if configured)
        llm_service_available = False
        if settings.llm_endpoint and settings.api_key:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        f"{settings.llm_endpoint}/models",
                        headers={"Authorization": f"Bearer {settings.api_key}"},
                    )
                    llm_service_available = response.status_code == 200
            except Exception as e:
                logger.warning(f"LLM service health check failed: {e}")
                llm_service_available = False

        # Get system resource usage (simplified)
        import psutil

        disk_usage = psutil.disk_usage("/").percent
        memory_usage = psutil.virtual_memory().percent

        # Check Redis connection
        redis_connected = True  # TODO: Implement Redis health check

        return SystemStatus(
            database_connected=database_connected,
            vector_db_connected=vector_db_connected,
            embedding_service_available=embedding_service_available,
            llm_service_available=llm_service_available,
            redis_connected=redis_connected,
            disk_usage_percent=disk_usage,
            memory_usage_percent=memory_usage,
        )
