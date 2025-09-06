"""Configuration management for ACP Ingest service."""

import os
from typing import Optional, List
from pydantic import BaseSettings, validator


class Settings(BaseSettings):
    """Application settings with validation."""

    # Application settings
    app_name: str = "ACP Ingest Service"
    version: str = "1.0.0"
    debug: bool = False
    environment: str = "production"

    # Server settings
    host: str = "127.0.0.1"  # Default to localhost for security
    port: int = 8000
    workers: int = 1
    reload: bool = False

    # Database settings
    database_url: str = "postgresql://acp:password@localhost/acp_ingest"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout: int = 30

    # Redis settings
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 10

    # Chroma settings
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_collection_name: str = "acp_knowledge"
    chroma_auth_token: Optional[str] = None

    # LLM settings
    llm_endpoint: str = "http://localhost:11434/v1"
    api_key: Optional[str] = None
    llm_model: str = "llama2"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2048
    llm_timeout: int = 60

    # Embedding settings
    embedding_endpoint: str = "http://localhost:11434/v1"
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768
    embedding_batch_size: int = 10
    embedding_timeout: int = 30

    # Security settings
    secret_key: str = "your-secret-key-change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours
    password_min_length: int = 8
    password_require_special: bool = True
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 30

    # Vault settings
    vault_url: Optional[str] = None
    vault_token: Optional[str] = None
    vault_namespace: Optional[str] = None
    vault_mount_point: str = "secret"
    vault_auth_method: str = "token"  # token, approle, kubernetes
    vault_role_id: Optional[str] = None
    vault_secret_id: Optional[str] = None
    vault_k8s_role: str = "acp-ingest"

    # RBAC settings
    rbac_enabled: bool = True
    default_user_role: str = "analyst"
    admin_users: List[str] = []

    # File upload settings
    max_file_size: int = 104857600  # 100MB
    upload_dir: str = "/app/uploads"
    allowed_extensions: List[str] = [
        "csv",
        "html",
        "htm",
        "xml",
        "pdf",
        "md",
        "txt",
        "zip",
        "json",
    ]
    temp_file_retention_hours: int = 24

    # Processing settings
    max_chunk_size: int = 1000
    chunk_overlap: int = 200
    batch_size: int = 10
    max_concurrent_jobs: int = 5
    job_timeout_minutes: int = 60
    retry_attempts: int = 3
    retry_delay_seconds: int = 30

    # PII detection settings
    pii_detection_enabled: bool = True
    pii_redaction_mode: str = "redact"  # redact, replace, mask
    pii_confidence_threshold: float = 0.8
    presidio_enabled: bool = False
    presidio_endpoint: Optional[str] = None
    custom_pii_patterns: List[str] = []

    # Audit settings
    audit_enabled: bool = True
    audit_retention_days: int = 2555  # 7 years
    audit_hash_algorithm: str = "sha256"
    audit_immutable: bool = True

    # Logging settings
    log_level: str = "INFO"
    log_format: str = "json"  # json, text
    log_file: Optional[str] = "/app/logs/acp-ingest.log"
    log_rotation: str = "1 day"
    log_retention: str = "30 days"
    structured_logging: bool = True

    # Monitoring settings
    prometheus_enabled: bool = False
    prometheus_port: int = 9090
    metrics_endpoint: str = "/metrics"
    health_check_interval: int = 30

    # Grafana settings
    grafana_enabled: bool = False
    grafana_port: int = 3000
    grafana_admin_password: str = "admin"

    # Export settings
    export_dir: str = "/app/exports"
    export_retention_hours: int = 48
    max_export_size: int = 1073741824  # 1GB
    export_formats: List[str] = ["csv", "json", "markdown", "html"]

    # Rate limiting settings
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 60
    rate_limit_burst: int = 10

    # CORS settings
    cors_enabled: bool = True
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    cors_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_headers: List[str] = ["*"]

    # SSL/TLS settings
    ssl_enabled: bool = False
    ssl_cert_file: Optional[str] = None
    ssl_key_file: Optional[str] = None
    ssl_ca_file: Optional[str] = None

    # Data retention settings
    data_retention_enabled: bool = True
    default_retention_days: int = 365
    sensitive_data_retention_days: int = 90
    audit_data_retention_days: int = 2555  # 7 years

    # Backup settings
    backup_enabled: bool = False
    backup_schedule: str = "0 2 * * *"  # Daily at 2 AM
    backup_retention_days: int = 30
    backup_location: str = "/app/backups"

    # Performance settings
    async_workers: int = 4
    connection_pool_size: int = 20
    query_timeout: int = 30
    bulk_insert_batch_size: int = 1000

    # Feature flags
    feature_advanced_search: bool = True
    feature_export_api: bool = True
    feature_audit_api: bool = True
    feature_metrics_api: bool = True
    feature_admin_api: bool = True

    # Development settings
    dev_mode: bool = False
    dev_auto_reload: bool = False
    dev_debug_sql: bool = False
    dev_mock_external_services: bool = False

    # Build information
    build_date: Optional[str] = None
    git_commit: Optional[str] = None
    build_number: Optional[str] = None

    @validator("admin_users", pre=True)
    def parse_admin_users(cls, v):
        if isinstance(v, str):
            return [user.strip() for user in v.split(",") if user.strip()]
        return v

    @validator("allowed_extensions", pre=True)
    def parse_allowed_extensions(cls, v):
        if isinstance(v, str):
            return [ext.strip().lower() for ext in v.split(",") if ext.strip()]
        return v

    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @validator("cors_methods", pre=True)
    def parse_cors_methods(cls, v):
        if isinstance(v, str):
            return [method.strip().upper() for method in v.split(",") if method.strip()]
        return v

    @validator("cors_headers", pre=True)
    def parse_cors_headers(cls, v):
        if isinstance(v, str):
            return [header.strip() for header in v.split(",") if header.strip()]
        return v

    @validator("custom_pii_patterns", pre=True)
    def parse_custom_pii_patterns(cls, v):
        if isinstance(v, str):
            return [pattern.strip() for pattern in v.split("|") if pattern.strip()]
        return v

    @validator("export_formats", pre=True)
    def parse_export_formats(cls, v):
        if isinstance(v, str):
            return [fmt.strip().lower() for fmt in v.split(",") if fmt.strip()]
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

        # Environment variable prefixes
        env_prefix = ""

        # Field aliases for environment variables
        fields = {
            "database_url": {"env": ["DATABASE_URL", "DB_URL"]},
            "redis_url": {"env": ["REDIS_URL", "CACHE_URL"]},
            "secret_key": {"env": ["SECRET_KEY", "JWT_SECRET"]},
            "api_key": {"env": ["API_KEY", "OPENAI_API_KEY", "LLM_API_KEY"]},
            "vault_token": {"env": ["VAULT_TOKEN", "VAULT_AUTH_TOKEN"]},
        }


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings


async def get_settings_with_vault() -> Settings:
    """Get application settings with Vault integration."""
    from .services.vault_service import vault_service

    # Initialize Vault if configured
    if settings.vault_url:
        await vault_service.initialize()

        # Override sensitive settings with Vault values
        if vault_service.authenticated:
            # Get database URL from Vault
            db_url = await vault_service.get_secret("acp/database", "url")
            if db_url:
                settings.database_url = db_url

            # Get Redis URL from Vault
            redis_url = await vault_service.get_secret("acp/redis", "url")
            if redis_url:
                settings.redis_url = redis_url

            # Get secret key from Vault
            secret_key = await vault_service.get_secret("acp/jwt", "secret_key")
            if secret_key:
                settings.secret_key = secret_key

            # Get API key from Vault
            api_key = await vault_service.get_secret("acp/llm", "api_key")
            if api_key:
                settings.api_key = api_key

    return settings


def is_development() -> bool:
    """Check if running in development mode."""
    return settings.environment.lower() in ["development", "dev", "local"]


def is_production() -> bool:
    """Check if running in production mode."""
    return settings.environment.lower() in ["production", "prod"]


def is_testing() -> bool:
    """Check if running in testing mode."""
    return settings.environment.lower() in ["testing", "test"]


def get_database_url() -> str:
    """Get database URL with proper formatting."""
    return settings.database_url


def get_redis_url() -> str:
    """Get Redis URL with proper formatting."""
    return settings.redis_url


def get_log_config() -> dict:
    """Get logging configuration."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
            },
        },
        "handlers": {
            "default": {
                "formatter": "json" if settings.log_format == "json" else "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            "file": (
                {
                    "formatter": "json" if settings.log_format == "json" else "default",
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": settings.log_file,
                    "maxBytes": 10485760,  # 10MB
                    "backupCount": 5,
                }
                if settings.log_file
                else None
            ),
        },
        "root": {
            "level": settings.log_level,
            "handlers": ["default"] + (["file"] if settings.log_file else []),
        },
    }


def validate_settings(settings_instance=None):
    """Validate critical settings."""
    if settings_instance is None:
        settings_instance = settings

    errors = []

    # Check required settings
    if (
        not settings_instance.secret_key
        or settings_instance.secret_key == "your-secret-key-change-this-in-production"
    ):  # nosec B105
        errors.append("SECRET_KEY must be set to a secure value in production")

    if settings_instance.is_production():
        if settings_instance.debug:
            errors.append("DEBUG should be False in production")

        if not settings_instance.ssl_enabled:
            errors.append("SSL should be enabled in production")

        if "*" in settings_instance.cors_origins:
            errors.append("CORS origins should be restricted in production")

    # Check Vault configuration
    if (
        settings_instance.vault_url
        and not settings_instance.vault_token
        and settings_instance.vault_auth_method == "token"
    ):
        errors.append("VAULT_TOKEN is required when using token authentication")

    # Check file paths
    import os

    if not os.path.exists(settings_instance.upload_dir):
        try:
            os.makedirs(settings_instance.upload_dir, exist_ok=True)
        except Exception as e:
            errors.append(
                f"Cannot create upload directory {settings_instance.upload_dir}: {e}"
            )

    if settings_instance.log_file:
        log_dir = os.path.dirname(settings_instance.log_file)
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create log directory {log_dir}: {e}")

    if errors:
        raise ValueError(
            "Configuration validation failed:\n"
            + "\n".join(f"- {error}" for error in errors)
        )


# Validate settings on import
if not is_testing():
    try:
        validate_settings()
    except ValueError as e:
        # In development, just warn about validation errors
        if is_development():
            print(f"Warning: {e}")
        else:
            raise
