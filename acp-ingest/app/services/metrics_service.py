"""Metrics service for observability and monitoring."""

import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, List, Optional

try:
    from prometheus_client import (
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        Info,
        generate_latest,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

from app.config import get_settings
from app.models import AuditLog, IngestJob, KnowledgeChunk
from app.utils.logging_config import get_logger
from sqlalchemy.orm import Session

logger = get_logger(__name__)
settings = get_settings()


class MetricsService:
    """Service for collecting and exposing application metrics."""

    def __init__(self):
        self.enabled = (
            getattr(settings, "PROMETHEUS_ENABLED", False) and PROMETHEUS_AVAILABLE
        )
        self.registry = CollectorRegistry() if self.enabled else None
        self._initialize_metrics()

    def _initialize_metrics(self):
        """Initialize Prometheus metrics."""
        if not self.enabled:
            logger.info("Metrics collection disabled or Prometheus not available")
            return

        # Counters
        self.ingest_jobs_total = Counter(
            "acp_ingest_jobs_total",
            "Total number of ingestion jobs",
            ["source_type", "status"],
            registry=self.registry,
        )

        self.search_queries_total = Counter(
            "acp_search_queries_total",
            "Total number of search queries",
            ["user_id"],
            registry=self.registry,
        )

        self.pii_detections_total = Counter(
            "acp_pii_detections_total",
            "Total number of PII detections",
            ["pii_type", "action"],
            registry=self.registry,
        )

        self.api_requests_total = Counter(
            "acp_api_requests_total",
            "Total number of API requests",
            ["method", "endpoint", "status_code"],
            registry=self.registry,
        )

        self.security_events_total = Counter(
            "acp_security_events_total",
            "Total number of security events",
            ["event_type", "severity"],
            registry=self.registry,
        )

        # Histograms
        self.ingest_duration_seconds = Histogram(
            "acp_ingest_duration_seconds",
            "Time spent processing ingestion jobs",
            ["source_type"],
            registry=self.registry,
        )

        self.search_duration_seconds = Histogram(
            "acp_search_duration_seconds",
            "Time spent processing search queries",
            registry=self.registry,
        )

        self.embedding_duration_seconds = Histogram(
            "acp_embedding_duration_seconds",
            "Time spent generating embeddings",
            registry=self.registry,
        )

        self.api_request_duration_seconds = Histogram(
            "acp_api_request_duration_seconds",
            "Time spent processing API requests",
            ["method", "endpoint"],
            registry=self.registry,
        )

        # Gauges
        self.active_jobs = Gauge(
            "acp_active_jobs",
            "Number of currently active ingestion jobs",
            registry=self.registry,
        )

        self.total_chunks = Gauge(
            "acp_total_chunks",
            "Total number of knowledge chunks",
            registry=self.registry,
        )

        self.database_connections = Gauge(
            "acp_database_connections",
            "Number of active database connections",
            registry=self.registry,
        )

        self.memory_usage_bytes = Gauge(
            "acp_memory_usage_bytes", "Memory usage in bytes", registry=self.registry
        )

        self.disk_usage_bytes = Gauge(
            "acp_disk_usage_bytes",
            "Disk usage in bytes",
            ["mount_point"],
            registry=self.registry,
        )

        # Info
        self.build_info = Info(
            "acp_build_info", "Build information", registry=self.registry
        )

        # Set build info
        self.build_info.info(
            {
                "version": getattr(settings, "VERSION", "unknown"),
                "build_date": getattr(settings, "BUILD_DATE", "unknown"),
                "git_commit": getattr(settings, "GIT_COMMIT", "unknown"),
            }
        )

        logger.info("Prometheus metrics initialized")

    def record_ingest_job(self, source_type: str, status: str):
        """Record an ingestion job completion."""
        if self.enabled:
            self.ingest_jobs_total.labels(source_type=source_type, status=status).inc()

    def record_search_query(self, user_id: str):
        """Record a search query."""
        if self.enabled:
            self.search_queries_total.labels(user_id=user_id).inc()

    def record_pii_detection(self, pii_type: str, action: str):
        """Record a PII detection event."""
        if self.enabled:
            self.pii_detections_total.labels(pii_type=pii_type, action=action).inc()

    def record_api_request(self, method: str, endpoint: str, status_code: int):
        """Record an API request."""
        if self.enabled:
            self.api_requests_total.labels(
                method=method, endpoint=endpoint, status_code=str(status_code)
            ).inc()

    def record_security_event(self, event_type: str, severity: str):
        """Record a security event."""
        if self.enabled:
            self.security_events_total.labels(
                event_type=event_type, severity=severity
            ).inc()

    @contextmanager
    def time_ingest_job(self, source_type: str):
        """Context manager to time ingestion jobs."""
        if self.enabled:
            with self.ingest_duration_seconds.labels(source_type=source_type).time():
                yield
        else:
            yield

    @contextmanager
    def time_search_query(self):
        """Context manager to time search queries."""
        if self.enabled:
            with self.search_duration_seconds.time():
                yield
        else:
            yield

    @contextmanager
    def time_embedding_generation(self):
        """Context manager to time embedding generation."""
        if self.enabled:
            with self.embedding_duration_seconds.time():
                yield
        else:
            yield

    @contextmanager
    def time_api_request(self, method: str, endpoint: str):
        """Context manager to time API requests."""
        if self.enabled:
            with self.api_request_duration_seconds.labels(
                method=method, endpoint=endpoint
            ).time():
                yield
        else:
            yield

    def update_active_jobs(self, count: int):
        """Update the number of active jobs."""
        if self.enabled:
            self.active_jobs.set(count)

    def update_total_chunks(self, count: int):
        """Update the total number of chunks."""
        if self.enabled:
            self.total_chunks.set(count)

    def update_database_connections(self, count: int):
        """Update the number of database connections."""
        if self.enabled:
            self.database_connections.set(count)

    def update_memory_usage(self, bytes_used: int):
        """Update memory usage."""
        if self.enabled:
            self.memory_usage_bytes.set(bytes_used)

    def update_disk_usage(self, mount_point: str, bytes_used: int):
        """Update disk usage for a mount point."""
        if self.enabled:
            self.disk_usage_bytes.labels(mount_point=mount_point).set(bytes_used)

    def collect_system_metrics(self, db: Session):
        """Collect system-wide metrics from the database."""
        if not self.enabled:
            return

        try:
            # Count active jobs
            active_jobs_count = (
                db.query(IngestJob)
                .filter(IngestJob.status.in_(["pending", "processing"]))
                .count()
            )
            self.update_active_jobs(active_jobs_count)

            # Count total chunks
            total_chunks_count = db.query(KnowledgeChunk).count()
            self.update_total_chunks(total_chunks_count)

            # Collect system resource metrics
            self._collect_resource_metrics()

        except Exception as e:
            logger.error("Error collecting system metrics", error=str(e))

    def _collect_resource_metrics(self):
        """Collect system resource metrics."""
        try:
            import psutil

            # Memory usage
            memory = psutil.virtual_memory()
            self.update_memory_usage(memory.used)

            # Disk usage
            disk_usage = psutil.disk_usage("/")
            self.update_disk_usage("/", disk_usage.used)

        except ImportError:
            logger.debug("psutil not available for resource metrics")
        except Exception as e:
            logger.error("Error collecting resource metrics", error=str(e))

    def get_metrics_summary(self, db: Session) -> Dict[str, Any]:
        """Get a summary of key metrics for dashboard display."""
        try:
            now = datetime.utcnow()
            last_24h = now - timedelta(hours=24)
            last_7d = now - timedelta(days=7)

            # Ingestion metrics
            total_jobs = db.query(IngestJob).count()
            jobs_24h = (
                db.query(IngestJob).filter(IngestJob.created_at >= last_24h).count()
            )
            jobs_7d = (
                db.query(IngestJob).filter(IngestJob.created_at >= last_7d).count()
            )

            completed_jobs = (
                db.query(IngestJob).filter(IngestJob.status == "completed").count()
            )
            failed_jobs = (
                db.query(IngestJob).filter(IngestJob.status == "failed").count()
            )
            active_jobs = (
                db.query(IngestJob)
                .filter(IngestJob.status.in_(["pending", "processing"]))
                .count()
            )

            # Success rate
            success_rate = (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0

            # Knowledge base metrics
            total_chunks = db.query(KnowledgeChunk).count()
            sensitive_chunks = (
                db.query(KnowledgeChunk)
                .filter(KnowledgeChunk.sensitive == True)
                .count()
            )

            # Audit metrics
            total_audit_events = db.query(AuditLog).count()
            audit_events_24h = (
                db.query(AuditLog).filter(AuditLog.created_at >= last_24h).count()
            )

            security_events_24h = (
                db.query(AuditLog)
                .filter(
                    AuditLog.created_at >= last_24h,
                    AuditLog.severity.in_(["high", "critical"]),
                )
                .count()
            )

            # Average processing time
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
                avg_processing_time = total_time / len(completed_jobs_with_time)
            else:
                avg_processing_time = 0

            return {
                "ingestion": {
                    "total_jobs": total_jobs,
                    "jobs_24h": jobs_24h,
                    "jobs_7d": jobs_7d,
                    "completed_jobs": completed_jobs,
                    "failed_jobs": failed_jobs,
                    "active_jobs": active_jobs,
                    "success_rate": round(success_rate, 2),
                    "avg_processing_time": round(avg_processing_time, 2),
                },
                "knowledge_base": {
                    "total_chunks": total_chunks,
                    "sensitive_chunks": sensitive_chunks,
                    "sensitivity_percentage": round(
                        (
                            (sensitive_chunks / total_chunks * 100)
                            if total_chunks > 0
                            else 0
                        ),
                        2,
                    ),
                },
                "security": {
                    "total_audit_events": total_audit_events,
                    "audit_events_24h": audit_events_24h,
                    "security_events_24h": security_events_24h,
                },
                "timestamp": now.isoformat(),
            }

        except Exception as e:
            logger.error("Error getting metrics summary", error=str(e))
            return {}

    def get_prometheus_metrics(self) -> str:
        """Get Prometheus-formatted metrics."""
        if not self.enabled:
            return "# Metrics collection disabled\n"

        try:
            return generate_latest(self.registry).decode("utf-8")
        except Exception as e:
            logger.error("Error generating Prometheus metrics", error=str(e))
            return f"# Error generating metrics: {str(e)}\n"

    def get_health_metrics(self) -> Dict[str, Any]:
        """Get health-related metrics for monitoring."""
        try:
            import psutil

            # System metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            # Network metrics
            network = psutil.net_io_counters()

            return {
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_available": memory.available,
                    "disk_percent": (disk.used / disk.total) * 100,
                    "disk_free": disk.free,
                },
                "network": {
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

        except ImportError:
            return {"error": "psutil not available for system metrics"}
        except Exception as e:
            logger.error("Error getting health metrics", error=str(e))
            return {"error": str(e)}


def timed_operation(metric_name: str, labels: Optional[Dict[str, str]] = None):
    """Decorator to time operations and record metrics."""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                # Record success metric
                if hasattr(metrics_service, metric_name):
                    histogram = getattr(metrics_service, metric_name)
                    if labels:
                        histogram.labels(**labels).observe(duration)
                    else:
                        histogram.observe(duration)

                return result
            except Exception as e:
                duration = time.time() - start_time

                # Record failure metric
                if hasattr(metrics_service, f"{metric_name}_failures"):
                    counter = getattr(metrics_service, f"{metric_name}_failures")
                    if labels:
                        counter.labels(**labels).inc()
                    else:
                        counter.inc()

                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                # Record success metric
                if hasattr(metrics_service, metric_name):
                    histogram = getattr(metrics_service, metric_name)
                    if labels:
                        histogram.labels(**labels).observe(duration)
                    else:
                        histogram.observe(duration)

                return result
            except Exception as e:
                duration = time.time() - start_time

                # Record failure metric
                if hasattr(metrics_service, f"{metric_name}_failures"):
                    counter = getattr(metrics_service, f"{metric_name}_failures")
                    if labels:
                        counter.labels(**labels).inc()
                    else:
                        counter.inc()

                raise

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Global metrics service instance
metrics_service = MetricsService()
