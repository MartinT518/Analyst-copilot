"""Configuration management for ACP Ingest service."""

import os
import sys
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


def is_testing() -> bool:
    """Check if we're running in a test environment."""
    return (
        "pytest" in sys.modules
        or "pytest" in sys.argv
        or os.getenv("TESTING", "").lower() in ("true", "1", "yes")
    )


class Settings(BaseSettings):
    """Application settings with validation."""

    # Application settings
    app_name: str = "ACP Ingest Service"
    version: str = "1.0.0"
    debug: bool = False
    DEBUG: bool = False  # Alias for compatibility

    # Security settings
    secret_key: str = ""
    SECRET_KEY: str = ""  # Alias for compatibility
    access_token_expire_minutes: int = 30
    algorithm: str = "HS256"

    # Database settings
    database_url: str = ""
    DATABASE_URL: str = ""  # Alias for compatibility
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "acp_ingest"
    database_user: str = "acp_user"
    database_password: str = ""

    # Redis settings
    redis_url: str = ""
    REDIS_URL: str = ""  # Alias for compatibility
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    # Vector database settings
    vector_db_url: str = ""
    vector_db_host: str = "localhost"
    vector_db_port: int = 6333
    vector_db_collection: str = "documents"

    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1
    api_reload: bool = False

    # CORS settings
    cors_origins: List[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]

    # File processing settings
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    allowed_file_types: List[str] = [
        ".pdf",
        ".doc",
        ".docx",
        ".txt",
        ".md",
        ".html",
        ".xml",
        ".json",
        ".csv",
        ".xlsx",
        ".pptx",
    ]
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # LLM settings
    llm_provider: str = "openai"
    llm_model: str = "gpt-3.5-turbo"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4000

    # Embedding settings
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-ada-002"
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_dimensions: int = 1536

    # Search settings
    search_limit: int = 20
    search_threshold: float = 0.7
    search_rerank: bool = True

    # Monitoring settings
    enable_metrics: bool = True
    metrics_port: int = 9090
    enable_tracing: bool = True
    tracing_endpoint: str = ""

    # Logging settings
    log_level: str = "INFO"
    log_format: str = "json"
    log_file: Optional[str] = None

    # Cache settings
    cache_ttl: int = 3600  # 1 hour
    cache_max_size: int = 1000

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds

    # Background tasks
    task_queue_size: int = 1000
    task_worker_count: int = 4
    task_timeout: int = 300  # 5 minutes

    # External services
    confluence_url: str = ""
    confluence_username: str = ""
    confluence_api_token: str = ""
    jira_url: str = ""
    jira_username: str = ""
    jira_api_token: str = ""

    # Security scanning
    enable_pii_detection: bool = True
    enable_content_scanning: bool = True
    sensitive_patterns: List[str] = [
        r"\b\d{4}-\d{4}-\d{4}-\d{4}\b",  # Credit card
        r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
    ]

    # Data retention
    data_retention_days: int = 365
    enable_auto_cleanup: bool = True
    cleanup_schedule: str = "0 2 * * *"  # Daily at 2 AM

    # Backup settings
    enable_backup: bool = True
    backup_schedule: str = "0 1 * * *"  # Daily at 1 AM
    backup_retention_days: int = 30

    # Performance settings
    max_concurrent_requests: int = 100
    request_timeout: int = 30
    connection_pool_size: int = 20

    # Feature flags
    enable_advanced_search: bool = True
    enable_semantic_search: bool = True
    enable_auto_categorization: bool = True
    enable_sentiment_analysis: bool = False

    # Development settings
    enable_swagger: bool = True
    enable_debug_toolbar: bool = False
    enable_profiling: bool = False

    # Environment-specific overrides
    environment: str = "development"
    testing: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @field_validator("secret_key", "SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Validate secret key is set."""
        if not v and not is_testing():
            raise ValueError("SECRET_KEY must be set")
        return v

    @field_validator("database_url", "DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL is set."""
        if not v and not is_testing():
            raise ValueError("DATABASE_URL must be set")
        return v

    @field_validator("redis_url", "REDIS_URL")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        """Validate Redis URL is set."""
        if not v and not is_testing():
            raise ValueError("REDIS_URL must be set")
        return v

    @field_validator("llm_api_key")
    @classmethod
    def validate_llm_api_key(cls, v: str) -> str:
        """Validate LLM API key is set."""
        if not v and not is_testing():
            raise ValueError("LLM API key must be set")
        return v

    @field_validator("embedding_api_key")
    @classmethod
    def validate_embedding_api_key(cls, v: str) -> str:
        """Validate embedding API key is set."""
        if not v and not is_testing():
            raise ValueError("Embedding API key must be set")
        return v

    @field_validator("max_file_size")
    @classmethod
    def validate_max_file_size(cls, v: int) -> int:
        """Validate max file size is reasonable."""
        if v <= 0:
            raise ValueError("Max file size must be positive")
        if v > 500 * 1024 * 1024:  # 500MB
            raise ValueError("Max file size cannot exceed 500MB")
        return v

    @field_validator("chunk_size")
    @classmethod
    def validate_chunk_size(cls, v: int) -> int:
        """Validate chunk size is reasonable."""
        if v <= 0:
            raise ValueError("Chunk size must be positive")
        if v > 10000:
            raise ValueError("Chunk size cannot exceed 10000")
        return v

    @field_validator("chunk_overlap")
    @classmethod
    def validate_chunk_overlap(cls, v: int) -> int:
        """Validate chunk overlap is reasonable."""
        if v < 0:
            raise ValueError("Chunk overlap cannot be negative")
        return v

    @field_validator("search_threshold")
    @classmethod
    def validate_search_threshold(cls, v: float) -> float:
        """Validate search threshold is in valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Search threshold must be between 0.0 and 1.0")
        return v

    @field_validator("llm_temperature")
    @classmethod
    def validate_llm_temperature(cls, v: float) -> float:
        """Validate LLM temperature is in valid range."""
        if not 0.0 <= v <= 2.0:
            raise ValueError("LLM temperature must be between 0.0 and 2.0")
        return v

    @field_validator("llm_max_tokens")
    @classmethod
    def validate_llm_max_tokens(cls, v: int) -> int:
        """Validate LLM max tokens is reasonable."""
        if v <= 0:
            raise ValueError("LLM max tokens must be positive")
        if v > 32000:
            raise ValueError("LLM max tokens cannot exceed 32000")
        return v

    @field_validator("embedding_dimensions")
    @classmethod
    def validate_embedding_dimensions(cls, v: int) -> int:
        """Validate embedding dimensions is reasonable."""
        if v <= 0:
            raise ValueError("Embedding dimensions must be positive")
        if v > 4096:
            raise ValueError("Embedding dimensions cannot exceed 4096")
        return v

    @field_validator("rate_limit_requests")
    @classmethod
    def validate_rate_limit_requests(cls, v: int) -> int:
        """Validate rate limit requests is reasonable."""
        if v <= 0:
            raise ValueError("Rate limit requests must be positive")
        return v

    @field_validator("rate_limit_window")
    @classmethod
    def validate_rate_limit_window(cls, v: int) -> int:
        """Validate rate limit window is reasonable."""
        if v <= 0:
            raise ValueError("Rate limit window must be positive")
        return v

    @field_validator("task_timeout")
    @classmethod
    def validate_task_timeout(cls, v: int) -> int:
        """Validate task timeout is reasonable."""
        if v <= 0:
            raise ValueError("Task timeout must be positive")
        return v

    @field_validator("data_retention_days")
    @classmethod
    def validate_data_retention_days(cls, v: int) -> int:
        """Validate data retention days is reasonable."""
        if v <= 0:
            raise ValueError("Data retention days must be positive")
        return v

    @field_validator("backup_retention_days")
    @classmethod
    def validate_backup_retention_days(cls, v: int) -> int:
        """Validate backup retention days is reasonable."""
        if v <= 0:
            raise ValueError("Backup retention days must be positive")
        return v

    @field_validator("max_concurrent_requests")
    @classmethod
    def validate_max_concurrent_requests(cls, v: int) -> int:
        """Validate max concurrent requests is reasonable."""
        if v <= 0:
            raise ValueError("Max concurrent requests must be positive")
        return v

    @field_validator("request_timeout")
    @classmethod
    def validate_request_timeout(cls, v: int) -> int:
        """Validate request timeout is reasonable."""
        if v <= 0:
            raise ValueError("Request timeout must be positive")
        return v

    @field_validator("connection_pool_size")
    @classmethod
    def validate_connection_pool_size(cls, v: int) -> int:
        """Validate connection pool size is reasonable."""
        if v <= 0:
            raise ValueError("Connection pool size must be positive")
        return v

    def validate_settings(self) -> None:
        """Validate all settings."""
        if not is_testing():
            # Only validate in non-testing environments
            if not self.secret_key and not self.SECRET_KEY:
                raise ValueError("SECRET_KEY must be set")
            if not self.database_url and not self.DATABASE_URL:
                raise ValueError("DATABASE_URL must be set")
            if not self.redis_url and not self.REDIS_URL:
                raise ValueError("REDIS_URL must be set")


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings


# Validate settings on import (skip in testing)
if not is_testing():
    try:
        settings.validate_settings()
    except ValueError as e:
        print(f"Configuration validation failed: {e}")
        sys.exit(1)
