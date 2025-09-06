"""Database models for the ACP Ingest service."""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    JSON,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

Base = declarative_base()


class User(Base):
    """User model for authentication and authorization."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    last_login = Column(DateTime(timezone=True))
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True))
    password_changed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user_roles = relationship("UserRole", back_populates="user")
    ingest_jobs = relationship("IngestJob", back_populates="uploader_user")
    audit_logs = relationship("AuditLog", back_populates="user")


class Role(Base):
    """Role model for RBAC."""

    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text)
    is_system_role = Column(Boolean, default=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user_roles = relationship("UserRole", back_populates="role")
    role_permissions = relationship("RolePermission", back_populates="role")


class Permission(Base):
    """Permission model for RBAC."""

    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text)
    resource_type = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    role_permissions = relationship("RolePermission", back_populates="permission")


class UserRole(Base):
    """User-Role association model."""

    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    assigned_by = Column(Integer, ForeignKey("users.id"))
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))

    # Relationships
    user = relationship("User", back_populates="user_roles", foreign_keys=[user_id])
    role = relationship("Role", back_populates="user_roles")
    assigner = relationship("User", foreign_keys=[assigned_by])

    # Constraints
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="unique_user_role"),)


class RolePermission(Base):
    """Role-Permission association model."""

    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    permission_id = Column(Integer, ForeignKey("permissions.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    role = relationship("Role", back_populates="role_permissions")
    permission = relationship("Permission", back_populates="role_permissions")

    # Constraints
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="unique_role_permission"),
    )


class IngestJob(Base):
    """Model for ingestion jobs."""

    __tablename__ = "ingest_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    source_type = Column(String(50), nullable=False, index=True)
    origin = Column(String(255), nullable=False)
    sensitivity = Column(String(20), nullable=False, index=True)
    uploader = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_path = Column(String(500))
    file_size = Column(Integer)
    original_filename = Column(String(255))
    status = Column(String(20), default="pending", index=True)
    error_message = Column(Text)
    chunks_created = Column(Integer, default=0)
    metadata = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    ingest_job_id = Column(UUID(as_uuid=True), ForeignKey("ingest_jobs.id"))
    source_type = Column(String(50), nullable=False, index=True)
    source_location = Column(String(500))
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer)
    metadata = Column(JSON)
    embedding_model = Column(String(100))
    embedding_version = Column(String(20))
    vector_id = Column(String(100), unique=True, index=True)
    sensitive = Column(Boolean, default=False, index=True)
    redacted = Column(Boolean, default=False)
    pii_types = Column(JSON)  # List of detected PII types
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

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

    id = Column(Integer, primary_key=True, index=True)
    chunk_id = Column(
        UUID(as_uuid=True), ForeignKey("knowledge_chunks.id"), nullable=False
    )
    pii_type = Column(String(50), nullable=False, index=True)
    confidence_score = Column(Integer)  # 0-100
    original_text = Column(Text)  # Encrypted/hashed original text for audit
    redacted_text = Column(Text)
    start_position = Column(Integer)
    end_position = Column(Integer)
    detection_method = Column(String(50))  # regex, ml_model, etc.
    reviewed = Column(Boolean, default=False)
    reviewed_by = Column(Integer, ForeignKey("users.id"))
    reviewed_at = Column(DateTime(timezone=True))
    false_positive = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    export_type = Column(
        String(50), nullable=False, index=True
    )  # search_results, audit_report, etc.
    format = Column(String(20), nullable=False)  # csv, json, markdown, html
    status = Column(String(20), default="pending", index=True)
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    parameters = Column(JSON)  # Export parameters
    file_path = Column(String(500))
    file_size = Column(Integer)
    record_count = Column(Integer)
    error_message = Column(Text)
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True))

    # Relationships
    requester = relationship("User")

    # Indexes
    __table_args__ = (
        Index("idx_export_jobs_status_created", "status", "created_at"),
        Index("idx_export_jobs_requester_created", "requested_by", "created_at"),
    )
