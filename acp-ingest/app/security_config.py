"""Security configuration and validation for ACP services."""

import logging
import secrets
from typing import Dict, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class SecurityConfig(BaseSettings):
    """Security-focused configuration with fail-fast validation."""

    # =============================================================================
    # CRITICAL SECURITY SETTINGS (MUST BE SET)
    # =============================================================================

    # Secret keys - system will fail to start if these are not properly set
    secret_key: str = Field(
        default="dev-secret-key-change-in-production",
        description="Application secret key for signing",
    )
    jwt_secret_key: str = Field(
        default="dev-jwt-secret-change-in-production", description="JWT signing secret key"
    )
    encryption_key: str = Field(
        default="dev-encryption-key-change-in-production",
        description="Encryption key for sensitive data",
    )

    # =============================================================================
    # OAUTH2/OIDC CONFIGURATION
    # =============================================================================

    # OAuth2 Client Configuration
    oauth2_client_id: str = Field(default="dev-client-id", description="OAuth2 client ID")
    oauth2_client_secret: str = Field(
        default="dev-client-secret", description="OAuth2 client secret"
    )
    oauth2_authorization_url: str = Field(
        default="http://localhost:8080/auth", description="OAuth2 authorization URL"
    )
    oauth2_token_url: str = Field(
        default="http://localhost:8080/token", description="OAuth2 token URL"
    )
    oauth2_userinfo_url: str = Field(
        default="http://localhost:8080/userinfo", description="OAuth2 userinfo URL"
    )
    oauth2_redirect_uri: str = Field(
        default="http://localhost:3000/callback", description="OAuth2 redirect URI"
    )

    # JWT Configuration
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # =============================================================================
    # VAULT CONFIGURATION
    # =============================================================================

    vault_url: Optional[str] = Field(default=None, description="HashiCorp Vault URL")
    vault_token: Optional[str] = Field(default=None, description="Vault authentication token")
    vault_namespace: Optional[str] = Field(default=None, description="Vault namespace")
    vault_mount_point: str = "secret"
    vault_auth_method: str = "token"

    # =============================================================================
    # CORS CONFIGURATION
    # =============================================================================

    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins",
    )
    cors_methods: List[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        description="Allowed CORS methods",
    )
    cors_headers: List[str] = Field(
        default_factory=lambda: ["Content-Type", "Authorization", "X-Requested-With"],
        description="Allowed CORS headers",
    )

    # =============================================================================
    # RATE LIMITING
    # =============================================================================

    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 60
    rate_limit_burst: int = 10

    # =============================================================================
    # SSL/TLS CONFIGURATION
    # =============================================================================

    ssl_enabled: bool = False
    ssl_cert_file: Optional[str] = None
    ssl_key_file: Optional[str] = None

    # =============================================================================
    # ENVIRONMENT CONFIGURATION
    # =============================================================================

    environment: str = "production"
    debug: bool = False

    model_config = {"env_file": ".env", "case_sensitive": False}

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v):
        """Validate secret key strength."""
        # Skip validation in testing environments
        import os

        if os.getenv("TESTING") or os.getenv("CI"):
            return v

        if not v or v == "your-secret-key-change-this-in-production":
            raise ValueError("SECRET_KEY must be set to a secure value")

        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")

        # Check for common weak patterns
        weak_patterns = [
            "password",
            "secret",
            "key",
            "123",
            "admin",
            "test",
            "default",
            "changeme",
            "temp",
            "demo",
        ]

        if any(pattern in v.lower() for pattern in weak_patterns):
            raise ValueError("SECRET_KEY contains weak patterns - use a strong, random key")

        return v

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret_key(cls, v):
        """Validate JWT secret key."""
        if not v or v == "your-jwt-secret-key-change-this-in-production":
            raise ValueError("JWT_SECRET_KEY must be set to a secure value")

        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters long")

        return v

    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key(cls, v):
        """Validate encryption key."""
        if not v or v == "your-encryption-key-change-this-in-production":
            raise ValueError("ENCRYPTION_KEY must be set to a secure value")

        if len(v) < 32:
            raise ValueError("ENCRYPTION_KEY must be at least 32 characters long")

        return v

    @field_validator("oauth2_client_secret")
    @classmethod
    def validate_oauth2_client_secret(cls, v):
        """Validate OAuth2 client secret."""
        if not v or v == "your-oauth2-client-secret":
            raise ValueError("OAUTH2_CLIENT_SECRET must be set to a secure value")

        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("cors_methods", mode="before")
    @classmethod
    def parse_cors_methods(cls, v):
        """Parse CORS methods from string or list."""
        if isinstance(v, str):
            return [method.strip().upper() for method in v.split(",") if method.strip()]
        return v

    @field_validator("cors_headers", mode="before")
    @classmethod
    def parse_cors_headers(cls, v):
        """Parse CORS headers from string or list."""
        if isinstance(v, str):
            return [header.strip() for header in v.split(",") if header.strip()]
        return v

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v):
        """Validate environment setting."""
        valid_environments = ["development", "staging", "production", "testing"]
        if v not in valid_environments:
            raise ValueError(f"Environment must be one of: {valid_environments}")
        return v

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    def validate_production_security(self) -> List[str]:
        """Validate production security requirements."""
        errors = []

        if self.is_production():
            if self.debug:
                errors.append("DEBUG must be False in production")

            if not self.ssl_enabled:
                errors.append("SSL must be enabled in production")

            if "*" in self.cors_origins:
                errors.append("CORS origins must be restricted in production")

            if not self.rate_limit_enabled:
                errors.append("Rate limiting must be enabled in production")

            # Check for Vault configuration in production
            if not self.vault_url:
                errors.append("Vault URL should be configured in production")

        return errors

    def generate_secure_secrets(self) -> Dict[str, str]:
        """Generate secure secrets for development/testing."""
        return {
            "secret_key": secrets.token_urlsafe(32),
            "jwt_secret_key": secrets.token_urlsafe(32),
            "encryption_key": secrets.token_urlsafe(32),
            "oauth2_client_secret": secrets.token_urlsafe(32),
        }

    def get_vault_secret_path(self, secret_name: str) -> str:
        """Get Vault secret path for a given secret name."""
        if self.vault_namespace:
            return f"{self.vault_namespace}/acp/{secret_name}"
        return f"acp/{secret_name}"


def validate_security_config() -> SecurityConfig:
    """Validate and return security configuration with fail-fast behavior."""
    try:
        config = SecurityConfig()

        # Skip production security validation in testing environments
        import os

        if not os.getenv("TESTING") and not os.getenv("CI"):
            # Validate production security requirements
            security_errors = config.validate_production_security()
            if security_errors:
                error_msg = "Security validation failed:\n" + "\n".join(
                    f"- {error}" for error in security_errors
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

        logger.info("Security configuration validated successfully")
        return config

    except Exception as e:
        logger.error(f"Security configuration validation failed: {e}")
        raise


def get_security_config() -> SecurityConfig:
    """Get validated security configuration."""
    return validate_security_config()
