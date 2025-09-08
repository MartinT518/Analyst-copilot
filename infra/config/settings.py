"""Pydantic settings for configuration validation and management."""

import os
from typing import List, Optional, Union
from pydantic import BaseSettings, Field, validator, SecretStr
from enum import Enum


class Environment(str, Enum):
    """Environment types."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class LogLevel(str, Enum):
    """Log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(str, Enum):
    """Log formats."""
    JSON = "json"
    TEXT = "text"


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""
    
    url: str = Field(..., env="DATABASE_URL")
    host: str = Field("localhost", env="DATABASE_HOST")
    port: int = Field(5432, env="DATABASE_PORT")
    name: str = Field("acp_db", env="DATABASE_NAME")
    user: str = Field("acp_user", env="DATABASE_USER")
    password: SecretStr = Field(..., env="DATABASE_PASSWORD")
    
    # Pool settings
    pool_size: int = Field(10, env="DATABASE_POOL_SIZE")
    max_overflow: int = Field(20, env="DATABASE_MAX_OVERFLOW")
    pool_timeout: int = Field(30, env="DATABASE_POOL_TIMEOUT")
    
    @validator("port")
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v
    
    class Config:
        env_prefix = "DATABASE_"


class RedisSettings(BaseSettings):
    """Redis configuration settings."""
    
    url: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    host: str = Field("localhost", env="REDIS_HOST")
    port: int = Field(6379, env="REDIS_PORT")
    db: int = Field(0, env="REDIS_DB")
    password: Optional[SecretStr] = Field(None, env="REDIS_PASSWORD")
    
    @validator("port")
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v
    
    @validator("db")
    def validate_db(cls, v):
        if not 0 <= v <= 15:
            raise ValueError("Redis DB must be between 0 and 15")
        return v
    
    class Config:
        env_prefix = "REDIS_"


class VectorDBSettings(BaseSettings):
    """Vector database configuration settings."""
    
    # Chroma settings
    chroma_host: str = Field("localhost", env="CHROMA_HOST")
    chroma_port: int = Field(8001, env="CHROMA_PORT")
    chroma_collection_name: str = Field("acp_documents", env="CHROMA_COLLECTION_NAME")
    
    # pgvector settings
    pgvector_enabled: bool = Field(False, env="PGVECTOR_ENABLED")
    pgvector_dimension: int = Field(1536, env="PGVECTOR_DIMENSION")
    
    @validator("chroma_port")
    def validate_chroma_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError("Chroma port must be between 1 and 65535")
        return v
    
    class Config:
        env_prefix = "VECTOR_"


class LLMSettings(BaseSettings):
    """LLM service configuration settings."""
    
    # OpenAI settings
    openai_api_key: SecretStr = Field(..., env="OPENAI_API_KEY")
    llm_endpoint: str = Field("https://api.openai.com/v1", env="LLM_ENDPOINT")
    embedding_endpoint: str = Field("https://api.openai.com/v1", env="EMBEDDING_ENDPOINT")
    
    # Local LLM settings
    local_llm_url: Optional[str] = Field(None, env="LOCAL_LLM_URL")
    local_llm_model: str = Field("qwen:latest", env="LOCAL_LLM_MODEL")
    local_llm_api_key: Optional[SecretStr] = Field(None, env="LOCAL_LLM_API_KEY")
    
    class Config:
        env_prefix = "LLM_"


class SecuritySettings(BaseSettings):
    """Security configuration settings."""
    
    # JWT settings
    secret_key: SecretStr = Field(..., env="SECRET_KEY")
    jwt_algorithm: str = Field("HS256", env="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(1440, env="JWT_EXPIRE_MINUTES")
    jwt_access_token_expire_minutes: int = Field(30, env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_refresh_token_expire_days: int = Field(7, env="JWT_REFRESH_TOKEN_EXPIRE_DAYS")
    
    # API Keys
    api_key_header: str = Field("X-API-Key", env="API_KEY_HEADER")
    default_api_key: Optional[SecretStr] = Field(None, env="DEFAULT_API_KEY")
    
    # CORS settings
    cors_origins: List[str] = Field(
        ["http://localhost:3000", "http://localhost:5173", "http://localhost:8080"],
        env="CORS_ORIGINS"
    )
    cors_allow_credentials: bool = Field(True, env="CORS_ALLOW_CREDENTIALS")
    cors_allow_methods: List[str] = Field(
        ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        env="CORS_ALLOW_METHODS"
    )
    cors_allow_headers: List[str] = Field(["*"], env="CORS_ALLOW_HEADERS")
    
    # Rate limiting
    rate_limit_requests_per_minute: int = Field(60, env="RATE_LIMIT_REQUESTS_PER_MINUTE")
    rate_limit_burst: int = Field(10, env="RATE_LIMIT_BURST")
    
    # Security headers
    secure_headers_enabled: bool = Field(True, env="SECURE_HEADERS_ENABLED")
    hsts_max_age: int = Field(31536000, env="HSTS_MAX_AGE")
    content_security_policy: str = Field("default-src 'self'", env="CONTENT_SECURITY_POLICY")
    
    @validator("secret_key")
    def validate_secret_key(cls, v):
        if len(v.get_secret_value()) < 32:
            raise ValueError("Secret key must be at least 32 characters long")
        return v
    
    @validator("jwt_algorithm")
    def validate_jwt_algorithm(cls, v):
        allowed_algorithms = ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"]
        if v not in allowed_algorithms:
            raise ValueError(f"JWT algorithm must be one of: {allowed_algorithms}")
        return v
    
    class Config:
        env_prefix = "SECURITY_"


class VaultSettings(BaseSettings):
    """HashiCorp Vault configuration settings."""
    
    enabled: bool = Field(False, env="VAULT_ENABLED")
    url: str = Field("http://localhost:8200", env="VAULT_URL")
    token: Optional[SecretStr] = Field(None, env="VAULT_TOKEN")
    mount_point: str = Field("secret", env="VAULT_MOUNT_POINT")
    secret_path: str = Field("acp", env="VAULT_SECRET_PATH")
    
    class Config:
        env_prefix = "VAULT_"


class ObservabilitySettings(BaseSettings):
    """Observability configuration settings."""
    
    # Logging
    log_level: LogLevel = Field(LogLevel.INFO, env="LOG_LEVEL")
    log_format: LogFormat = Field(LogFormat.JSON, env="LOG_FORMAT")
    log_file: Optional[str] = Field(None, env="LOG_FILE")
    log_max_size: str = Field("100MB", env="LOG_MAX_SIZE")
    log_backup_count: int = Field(5, env="LOG_BACKUP_COUNT")
    
    # Metrics
    metrics_enabled: bool = Field(True, env="METRICS_ENABLED")
    prometheus_enabled: bool = Field(False, env="PROMETHEUS_ENABLED")
    metrics_port: int = Field(9090, env="METRICS_PORT")
    prometheus_multiproc_dir: str = Field("/tmp/prometheus_multiproc", env="PROMETHEUS_MULTIPROC_DIR")
    
    # Tracing
    tracing_enabled: bool = Field(False, env="TRACING_ENABLED")
    jaeger_agent_host: str = Field("localhost", env="JAEGER_AGENT_HOST")
    jaeger_agent_port: int = Field(6831, env="JAEGER_AGENT_PORT")
    jaeger_service_name: str = Field("analyst-copilot", env="JAEGER_SERVICE_NAME")
    
    # Health checks
    health_check_timeout: int = Field(30, env="HEALTH_CHECK_TIMEOUT")
    health_check_interval: int = Field(60, env="HEALTH_CHECK_INTERVAL")
    
    @validator("metrics_port")
    def validate_metrics_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError("Metrics port must be between 1 and 65535")
        return v
    
    class Config:
        env_prefix = "OBSERVABILITY_"


class ServiceSettings(BaseSettings):
    """Service configuration settings."""
    
    # Ingest service
    ingest_host: str = Field("0.0.0.0", env="INGEST_SERVICE_HOST")
    ingest_port: int = Field(8000, env="INGEST_SERVICE_PORT")
    ingest_workers: int = Field(4, env="INGEST_SERVICE_WORKERS")
    ingest_reload: bool = Field(False, env="INGEST_SERVICE_RELOAD")
    
    # Agents service
    agents_host: str = Field("0.0.0.0", env="AGENTS_SERVICE_HOST")
    agents_port: int = Field(8001, env="AGENTS_SERVICE_PORT")
    agents_workers: int = Field(4, env="AGENTS_SERVICE_WORKERS")
    agents_reload: bool = Field(False, env="AGENTS_SERVICE_RELOAD")
    
    # Code analyzer service
    code_analyzer_host: str = Field("0.0.0.0", env="CODE_ANALYZER_SERVICE_HOST")
    code_analyzer_port: int = Field(8002, env="CODE_ANALYZER_SERVICE_PORT")
    code_analyzer_workers: int = Field(2, env="CODE_ANALYZER_SERVICE_WORKERS")
    code_analyzer_reload: bool = Field(False, env="CODE_ANALYZER_SERVICE_RELOAD")
    
    @validator("ingest_port", "agents_port", "code_analyzer_port")
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v
    
    class Config:
        env_prefix = "SERVICE_"


class FileProcessingSettings(BaseSettings):
    """File processing configuration settings."""
    
    # Upload limits
    max_file_size: str = Field("100MB", env="MAX_FILE_SIZE")
    upload_dir: str = Field("/app/uploads", env="UPLOAD_DIR")
    allowed_extensions: List[str] = Field(
        ["csv", "html", "htm", "xml", "pdf", "md", "txt", "zip", "json"],
        env="ALLOWED_EXTENSIONS"
    )
    
    # Processing settings
    max_chunk_size: int = Field(1000, env="MAX_CHUNK_SIZE")
    chunk_overlap: int = Field(200, env="CHUNK_OVERLAP")
    batch_size: int = Field(10, env="BATCH_SIZE")
    max_concurrent_jobs: int = Field(5, env="MAX_CONCURRENT_JOBS")
    
    # OCR settings
    ocr_enabled: bool = Field(True, env="OCR_ENABLED")
    ocr_language: str = Field("eng", env="OCR_LANGUAGE")
    ocr_dpi: int = Field(300, env="OCR_DPI")
    
    # PII detection
    pii_detection_enabled: bool = Field(True, env="PII_DETECTION_ENABLED")
    pii_redaction_enabled: bool = Field(True, env="PII_REDACTION_ENABLED")
    pii_confidence_threshold: float = Field(0.8, env="PII_CONFIDENCE_THRESHOLD")
    presidio_enabled: bool = Field(False, env="PRESIDIO_ENABLED")
    
    @validator("pii_confidence_threshold")
    def validate_confidence_threshold(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("PII confidence threshold must be between 0.0 and 1.0")
        return v
    
    class Config:
        env_prefix = "FILE_"


class ACPSettings(BaseSettings):
    """Main ACP configuration settings."""
    
    # Environment
    environment: Environment = Field(Environment.DEVELOPMENT, env="ENVIRONMENT")
    debug: bool = Field(False, env="DEBUG")
    testing: bool = Field(False, env="TESTING")
    
    # Component settings
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    vector_db: VectorDBSettings = VectorDBSettings()
    llm: LLMSettings = LLMSettings()
    security: SecuritySettings = SecuritySettings()
    vault: VaultSettings = VaultSettings()
    observability: ObservabilitySettings = ObservabilitySettings()
    services: ServiceSettings = ServiceSettings()
    file_processing: FileProcessingSettings = FileProcessingSettings()
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    @validator("environment", pre=True)
    def validate_environment(cls, v):
        if isinstance(v, str):
            return Environment(v.lower())
        return v
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == Environment.PRODUCTION
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == Environment.DEVELOPMENT
    
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.environment == Environment.TESTING or self.testing


# Global settings instance
settings = ACPSettings()

