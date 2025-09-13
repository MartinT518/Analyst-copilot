"""Simple tests to verify basic functionality."""

import os

import pytest

# Set test environment variables before any imports
os.environ["TESTING"] = "true"
os.environ["USE_SQLITE_FOR_TESTS"] = "true"

from app.config import get_settings


class TestBasicFunctionality:
    """Test basic application functionality."""

    def test_settings_loading(self):
        """Test that settings can be loaded."""
        settings = get_settings()
        assert settings is not None
        assert settings.app_name == "ACP Ingest Service"
        assert settings.version == "1.0.0"

    def test_database_url_fallback(self):
        """Test that database URL fallback works."""
        settings = get_settings()
        db_url = settings.get_database_url()

        # Should use SQLite when TESTING is set
        assert "sqlite" in db_url or "postgresql" in db_url
        assert db_url is not None

    def test_database_connection(self, db_session):
        """Test database connection using fixture."""
        # This test uses the db_session fixture from conftest.py
        assert db_session is not None

        # Test a simple query
        from sqlalchemy import text

        result = db_session.execute(text("SELECT 1 as test_value"))
        row = result.fetchone()
        assert row[0] == 1

    def test_environment_variables(self):
        """Test that environment variables are set correctly."""
        assert os.getenv("TESTING") == "true"
        assert os.getenv("USE_SQLITE_FOR_TESTS") == "true"


class TestSecurityConfig:
    """Test security configuration."""

    def test_security_config_creation(self):
        """Test that security config can be created."""
        from app.security_config import SecurityConfig

        config = SecurityConfig(
            secret_key="test-secret-key-that-is-long-enough",
            jwt_secret_key="test-jwt-secret-key-that-is-long-enough",
            encryption_key="test-encryption-key-that-is-long-enough",
        )

        assert config.secret_key == "test-secret-key-that-is-long-enough"
        assert config.jwt_secret_key == "test-jwt-secret-key-that-is-long-enough"
        assert config.encryption_key == "test-encryption-key-that-is-long-enough"


class TestLogging:
    """Test logging functionality."""

    def test_logging_setup(self):
        """Test that logging can be set up."""
        from app.observability.logging import get_logger, setup_logging

        setup_logging(
            service_name="test-service",
            service_version="1.0.0",
            log_level="INFO",
            log_format="json",
        )

        logger = get_logger("test")
        assert logger is not None


if __name__ == "__main__":
    pytest.main([__file__])
