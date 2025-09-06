"""Configuration settings for the ACP Code Analyzer service."""

import os
from typing import Optional, List
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # Application
    app_name: str = "ACP Code Analyzer"
    version: str = "1.0.0"
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    
    # API
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8002, env="API_PORT")
    api_prefix: str = Field(default="/api/v1", env="API_PREFIX")
    
    # Database
    database_url: str = Field(
        default="postgresql://acp_user:acp_password@localhost:5432/acp_code_analyzer",
        env="DATABASE_URL"
    )
    
    # Ingest service integration
    ingest_service_url: str = Field(
        default="http://localhost:8000",
        env="INGEST_SERVICE_URL"
    )
    ingest_service_api_key: Optional[str] = Field(default=None, env="INGEST_SERVICE_API_KEY")
    
    # Code analysis settings
    max_file_size_mb: int = Field(default=10, env="MAX_FILE_SIZE_MB")
    supported_languages: List[str] = Field(
        default=["python", "javascript", "typescript", "java", "go", "rust", "sql"],
        env="SUPPORTED_LANGUAGES"
    )
    analysis_timeout_seconds: int = Field(default=300, env="ANALYSIS_TIMEOUT_SECONDS")
    
    # Git repository settings
    max_repo_size_mb: int = Field(default=500, env="MAX_REPO_SIZE_MB")
    clone_timeout_seconds: int = Field(default=600, env="CLONE_TIMEOUT_SECONDS")
    temp_repo_dir: str = Field(default="/tmp/acp_repos", env="TEMP_REPO_DIR")
    
    # Database schema analysis
    db_connection_timeout: int = Field(default=30, env="DB_CONNECTION_TIMEOUT")
    max_tables_per_analysis: int = Field(default=100, env="MAX_TABLES_PER_ANALYSIS")
    
    # Processing limits
    max_concurrent_analyses: int = Field(default=5, env="MAX_CONCURRENT_ANALYSES")
    chunk_size_lines: int = Field(default=100, env="CHUNK_SIZE_LINES")
    max_chunks_per_file: int = Field(default=50, env="MAX_CHUNKS_PER_FILE")
    
    # Security
    allowed_file_extensions: List[str] = Field(
        default=[
            ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".sql",
            ".md", ".txt", ".json", ".yaml", ".yml", ".xml", ".html", ".css"
        ],
        env="ALLOWED_FILE_EXTENSIONS"
    )
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")
    
    # Metrics
    metrics_enabled: bool = Field(default=True, env="METRICS_ENABLED")
    metrics_port: int = Field(default=9002, env="METRICS_PORT")
    
    class Config:
        """Pydantic config."""
        env_file = ".env"
        case_sensitive = False


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get application settings.
    
    Returns:
        Settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment.
    
    Returns:
        New settings instance
    """
    global _settings
    _settings = Settings()
    return _settings

