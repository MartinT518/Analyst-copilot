"""Configuration management for ACP Agents service."""

from typing import List, Optional

from pydantic import BaseSettings, validator


class Settings(BaseSettings):
    """Application settings for the agents microservice."""

    # Application settings
    app_name: str = "ACP Agents Service"
    version: str = "1.0.0"
    debug: bool = False
    environment: str = "production"

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8001
    workers: int = 1
    reload: bool = False

    # Database settings (shared with ingest service)
    database_url: str = "postgresql://acp:password@localhost/acp_ingest"

    # Redis settings
    redis_url: str = "redis://localhost:6379/1"  # Different DB from ingest

    # LLM settings for agents
    llm_endpoint: str = "http://localhost:11434/v1"
    api_key: Optional[str] = None
    llm_model: str = "qwen2.5:14b"  # Default to Qwen model
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096
    llm_timeout: int = 120

    # Embedding settings (for knowledge retrieval)
    embedding_endpoint: str = "http://localhost:11434/v1"
    embedding_model: str = "nomic-embed-text"

    # Ingest service integration
    ingest_service_url: str = "http://localhost:8000"
    ingest_service_api_key: Optional[str] = None

    # Security settings
    secret_key: str = "your-secret-key-change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # Agent workflow settings
    max_workflow_steps: int = 20
    workflow_timeout_minutes: int = 30
    max_concurrent_workflows: int = 10

    # Agent-specific settings
    clarifier_max_questions: int = 5
    synthesizer_max_sections: int = 10
    taskmaster_max_tasks: int = 20
    verifier_confidence_threshold: float = 0.8

    # JSON schema validation
    strict_schema_validation: bool = True
    schema_validation_timeout: int = 10

    # Audit settings
    audit_enabled: bool = True
    audit_agent_steps: bool = True
    audit_provenance: bool = True

    # Logging settings
    log_level: str = "INFO"
    log_format: str = "json"
    structured_logging: bool = True

    # Monitoring settings
    prometheus_enabled: bool = False
    metrics_endpoint: str = "/metrics"

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 30

    # CORS settings
    cors_enabled: bool = True
    cors_origins: List[str] = ["*"]
    cors_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_headers: List[str] = ["*"]

    # Workflow persistence
    persist_workflows: bool = True
    workflow_retention_days: int = 30

    # Agent prompt templates directory
    prompt_templates_dir: str = "/app/templates"

    # Knowledge base integration
    kb_search_limit: int = 10
    kb_similarity_threshold: float = 0.7

    # Development settings
    dev_mode: bool = False
    dev_mock_llm: bool = False
    dev_debug_workflows: bool = False

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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

        # Environment variable prefixes
        env_prefix = "AGENTS_"

        # Field aliases for environment variables
        fields = {
            "database_url": {"env": ["AGENTS_DATABASE_URL", "DATABASE_URL"]},
            "redis_url": {"env": ["AGENTS_REDIS_URL", "REDIS_URL"]},
            "secret_key": {"env": ["AGENTS_SECRET_KEY", "SECRET_KEY"]},
            "api_key": {"env": ["AGENTS_API_KEY", "API_KEY", "OPENAI_API_KEY", "LLM_API_KEY"]},
        }


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
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


def validate_settings():
    """Validate critical settings."""
    errors = []

    # Check required settings
    if (
        not settings.secret_key
        or settings.secret_key == "your-secret-key-change-this-in-production"
    ):
        errors.append("SECRET_KEY must be set to a secure value in production")

    if not settings.llm_endpoint:
        errors.append("LLM_ENDPOINT must be configured")

    if not settings.ingest_service_url:
        errors.append("INGEST_SERVICE_URL must be configured")

    if is_production():
        if settings.debug:
            errors.append("DEBUG should be False in production")

        if settings.cors_origins == ["*"]:
            errors.append("CORS origins should be restricted in production")

    # Check file paths
    import os

    if not os.path.exists(settings.prompt_templates_dir):
        try:
            os.makedirs(settings.prompt_templates_dir, exist_ok=True)
        except Exception as e:
            errors.append(f"Cannot create templates directory {settings.prompt_templates_dir}: {e}")

    if errors:
        raise ValueError(
            "Configuration validation failed:\n" + "\n".join(f"- {error}" for error in errors)
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
