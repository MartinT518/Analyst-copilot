"""Database models for the ACP Ingest service."""

import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all database models."""


class User(Base):
    """User model for authentication and authorization."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    user_roles = relationship("UserRole", back_populates="user")
    ingest_jobs = relationship("IngestJob", back_populates="uploader_user")
    audit_logs = relationship("AuditLog", back_populates="user")


class Role(Base):
    """Role model for RBAC."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system_role: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    user_roles = relationship("UserRole", back_populates="role")
    role_permissions = relationship("RolePermission", back_populates="role")


class Permission(Base):
    """Permission model for RBAC."""

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    resource_type: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    role_permissions = relationship("RolePermission", back_populates="permission")


class UserRole(Base):
    """User-Role association model."""

    __tablename__ = "user_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"), nullable=False)
    assigned_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    assigned_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    user = relationship("User", back_populates="user_roles", foreign_keys=[user_id])
    role = relationship("Role", back_populates="user_roles")
    assigner = relationship("User", foreign_keys=[assigned_by])

    # Constraints
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="unique_user_role"),)


class RolePermission(Base):
    """Role-Permission association model."""

    __tablename__ = "role_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"), nullable=False)
    permission_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("permissions.id"), nullable=False
    )
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    role = relationship("Role", back_populates="role_permissions")
    permission = relationship("Permission", back_populates="role_permissions")

    # Constraints
    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="unique_role_permission"),)


class IngestJob(Base):
    """Model for ingestion jobs."""

    __tablename__ = "ingest_jobs"

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    origin: Mapped[str] = mapped_column(String(255), nullable=False)
    sensitivity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    uploader: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(500))
    file_size: Mapped[int | None] = mapped_column(Integer)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    chunks_created: Mapped[int] = mapped_column(Integer, default=0)
    job_metadata: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    uploader_user = relationship("User", back_populates="ingest_jobs")
    knowledge_chunks = relationship("KnowledgeChunk", back_populates="ingest_job")

    # Indexes
    __table_args__ = (
        Index("idx_ingest_jobs_status_created", "status", "created_at"),
        Index("idx_ingest_jobs_uploader_created", "uploader", "created_at"),
    )


class KnowledgeChunk(Base):
    """Model for knowledge chunks."""

    __tablename__ = "knowledge_chunks"

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    ingest_job_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("ingest_jobs.id")
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_location: Mapped[str | None] = mapped_column(String(500))
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int | None] = mapped_column(Integer)
    chunk_metadata: Mapped[dict | None] = mapped_column(JSON)
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    embedding_version: Mapped[str | None] = mapped_column(String(20))
    vector_id: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    sensitive: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    redacted: Mapped[bool] = mapped_column(Boolean, default=False)
    pii_types: Mapped[list | None] = mapped_column(JSON)  # List of detected PII types
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    ingest_job = relationship("IngestJob", back_populates="knowledge_chunks")

    # Indexes
    __table_args__ = (
        Index("idx_knowledge_chunks_source_sensitive", "source_type", "sensitive"),
        Index("idx_knowledge_chunks_created", "created_at"),
    )


class AuditLog(Base):
    """Model for audit logs with immutable hash chain."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    resource_type = Column(String(50), index=True)
    resource_id = Column(String(100), index=True)
    details = Column(JSON)
    severity = Column(String(20), nullable=False, index=True)
    ip_address = Column(String(45))  # IPv6 compatible
    user_agent = Column(Text)
    hash = Column(String(64), nullable=False, unique=True)  # SHA-256 hash
    previous_hash = Column(String(64))  # For chain integrity
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    user = relationship("User", back_populates="audit_logs")

    # Indexes
    __table_args__ = (
        Index("idx_audit_logs_action_created", "action", "created_at"),
        Index("idx_audit_logs_user_created", "user_id", "created_at"),
        Index("idx_audit_logs_severity_created", "severity", "created_at"),
        Index("idx_audit_logs_resource", "resource_type", "resource_id"),
    )


class APIKey(Base):
    """Model for API keys."""

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    scopes = Column(JSON)  # List of allowed scopes/permissions
    is_active = Column(Boolean, default=True)
    last_used = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User")


class SystemConfig(Base):
    """Model for system configuration."""

    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(JSON)
    description = Column(Text)
    is_sensitive = Column(Boolean, default=False)
    updated_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    updater = relationship("User")


class DataRetentionPolicy(Base):
    """Model for data retention policies."""

    __tablename__ = "data_retention_policies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    resource_type = Column(String(50), nullable=False)
    sensitivity_level = Column(String(20))
    retention_days = Column(Integer, nullable=False)
    auto_delete = Column(Boolean, default=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    creator = relationship("User")


class SecurityEvent(Base):
    """Model for security events and alerts."""

    __tablename__ = "security_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    user_id = Column(Integer, ForeignKey("users.id"))
    ip_address = Column(String(45))
    user_agent = Column(Text)
    metadata = Column(JSON)
    status = Column(
        String(20), default="open", index=True
    )  # open, investigating, resolved, false_positive
    resolved_by = Column(Integer, ForeignKey("users.id"))
    resolved_at = Column(DateTime(timezone=True))
    resolution_notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    resolver = relationship("User", foreign_keys=[resolved_by])

    # Indexes
    __table_args__ = (
        Index("idx_security_events_type_severity", "event_type", "severity"),
        Index("idx_security_events_status_created", "status", "created_at"),
    )


class PIIDetection(Base):
    """Model for PII detection results."""

    __tablename__ = "pii_detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chunk_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("knowledge_chunks.id"), nullable=False
    )
    pii_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    confidence_score: Mapped[int | None] = mapped_column(Integer)  # 0-100
    original_text: Mapped[str | None] = mapped_column(
        Text
    )  # Encrypted/hashed original text for audit
    redacted_text: Mapped[str | None] = mapped_column(Text)
    start_position: Mapped[int | None] = mapped_column(Integer)
    end_position: Mapped[int | None] = mapped_column(Integer)
    detection_method: Mapped[str | None] = mapped_column(String(50))  # regex, ml_model, etc.
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    false_positive: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    # Relationships
    chunk = relationship("KnowledgeChunk")
    reviewer = relationship("User")

    # Indexes
    __table_args__ = (
        Index("idx_pii_detections_type_created", "pii_type", "created_at"),
        Index("idx_pii_detections_chunk_type", "chunk_id", "pii_type"),
    )


class ExportJob(Base):
    """Model for export jobs."""

    __tablename__ = "export_jobs"

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    export_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # search_results, audit_report, etc.
    format: Mapped[str] = mapped_column(String(20), nullable=False)  # csv, json, markdown, html
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    requested_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    parameters: Mapped[dict | None] = mapped_column(JSON)  # Export parameters
    file_path: Mapped[str | None] = mapped_column(String(500))
    file_size: Mapped[int | None] = mapped_column(Integer)
    record_count: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    requester = relationship("User")

    # Indexes
    __table_args__ = (
        Index("idx_export_jobs_status_created", "status", "created_at"),
        Index("idx_export_jobs_requester_created", "requested_by", "created_at"),
    )
