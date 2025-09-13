"""HashiCorp Vault client for secrets management."""

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class VaultClientInterface(ABC):
    """Interface for Vault client implementations."""

    @abstractmethod
    def get_secret(self, path: str) -> Dict[str, Any]:
        """Get a secret from Vault."""
        pass

    @abstractmethod
    def put_secret(self, path: str, secret: Dict[str, Any]) -> bool:
        """Put a secret to Vault."""
        pass

    @abstractmethod
    def delete_secret(self, path: str) -> bool:
        """Delete a secret from Vault."""
        pass

    @abstractmethod
    def is_healthy(self) -> bool:
        """Check if Vault is healthy and accessible."""
        pass


class HashiCorpVaultClient(VaultClientInterface):
    """HashiCorp Vault client implementation."""

    def __init__(self, url: str, token: str, mount_point: str = "secret", timeout: int = 30):
        """Initialize Vault client.

        Args:
            url: Vault server URL
            token: Vault authentication token
            mount_point: Vault mount point
            timeout: Request timeout in seconds
        """
        self.url = url.rstrip("/")
        self.token = token
        self.mount_point = mount_point
        self.timeout = timeout

        # Import hvac only if Vault is enabled
        try:
            import hvac

            self.client = hvac.Client(url=self.url, token=self.token)
        except ImportError:
            logger.warning("hvac library not installed. Vault functionality will be limited.")
            self.client = None

    def get_secret(self, path: str) -> Dict[str, Any]:
        """Get a secret from Vault.

        Args:
            path: Secret path

        Returns:
            Secret data
        """
        if not self.client:
            raise RuntimeError("Vault client not available. Install hvac library.")

        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path, mount_point=self.mount_point
            )
            return response["data"]["data"]
        except Exception as e:
            logger.error(f"Failed to get secret from Vault: {e}")
            raise

    def put_secret(self, path: str, secret: Dict[str, Any]) -> bool:
        """Put a secret to Vault.

        Args:
            path: Secret path
            secret: Secret data

        Returns:
            True if successful
        """
        if not self.client:
            raise RuntimeError("Vault client not available. Install hvac library.")

        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path, secret=secret, mount_point=self.mount_point
            )
            return True
        except Exception as e:
            logger.error(f"Failed to put secret to Vault: {e}")
            return False

    def delete_secret(self, path: str) -> bool:
        """Delete a secret from Vault.

        Args:
            path: Secret path

        Returns:
            True if successful
        """
        if not self.client:
            raise RuntimeError("Vault client not available. Install hvac library.")

        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=path, mount_point=self.mount_point
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete secret from Vault: {e}")
            return False

    def is_healthy(self) -> bool:
        """Check if Vault is healthy and accessible.

        Returns:
            True if healthy
        """
        if not self.client:
            return False

        try:
            return self.client.sys.is_initialized() and not self.client.sys.is_sealed()
        except Exception as e:
            logger.error(f"Vault health check failed: {e}")
            return False


class MockVaultClient(VaultClientInterface):
    """Mock Vault client for development and testing."""

    def __init__(self):
        """Initialize mock Vault client."""
        self.secrets: Dict[str, Dict[str, Any]] = {}
        logger.info("Using mock Vault client for development")

    def get_secret(self, path: str) -> Dict[str, Any]:
        """Get a secret from mock storage.

        Args:
            path: Secret path

        Returns:
            Secret data
        """
        if path not in self.secrets:
            raise KeyError(f"Secret not found: {path}")
        return self.secrets[path]

    def put_secret(self, path: str, secret: Dict[str, Any]) -> bool:
        """Put a secret to mock storage.

        Args:
            path: Secret path
            secret: Secret data

        Returns:
            True if successful
        """
        self.secrets[path] = secret
        return True

    def delete_secret(self, path: str) -> bool:
        """Delete a secret from mock storage.

        Args:
            path: Secret path

        Returns:
            True if successful
        """
        if path in self.secrets:
            del self.secrets[path]
        return True

    def is_healthy(self) -> bool:
        """Check if mock Vault is healthy.

        Returns:
            Always True for mock client
        """
        return True


class VaultManager:
    """Vault manager for secrets operations."""

    def __init__(
        self,
        enabled: bool = False,
        url: Optional[str] = None,
        token: Optional[str] = None,
        mount_point: str = "secret",
        secret_path: str = "acp",
    ):
        """Initialize Vault manager.

        Args:
            enabled: Whether Vault is enabled
            url: Vault server URL
            token: Vault authentication token
            mount_point: Vault mount point
            secret_path: Base secret path
        """
        self.enabled = enabled
        self.secret_path = secret_path

        if enabled and url and token:
            self.client = HashiCorpVaultClient(url, token, mount_point)
        else:
            self.client = MockVaultClient()

    def get_database_credentials(self) -> Dict[str, str]:
        """Get database credentials from Vault.

        Returns:
            Database credentials
        """
        if self.enabled:
            try:
                return self.client.get_secret(f"{self.secret_path}/database")
            except Exception as e:
                logger.warning(f"Failed to get database credentials from Vault: {e}")

        # Fallback to environment variables
        return {
            "host": os.getenv("DATABASE_HOST", "localhost"),
            "port": os.getenv("DATABASE_PORT", "5432"),
            "name": os.getenv("DATABASE_NAME", "acp_db"),
            "user": os.getenv("DATABASE_USER", "acp_user"),
            "password": os.getenv("DATABASE_PASSWORD", "acp_password"),
        }

    def get_redis_credentials(self) -> Dict[str, str]:
        """Get Redis credentials from Vault.

        Returns:
            Redis credentials
        """
        if self.enabled:
            try:
                return self.client.get_secret(f"{self.secret_path}/redis")
            except Exception as e:
                logger.warning(f"Failed to get Redis credentials from Vault: {e}")

        # Fallback to environment variables
        return {
            "host": os.getenv("REDIS_HOST", "localhost"),
            "port": os.getenv("REDIS_PORT", "6379"),
            "password": os.getenv("REDIS_PASSWORD", ""),
        }

    def get_llm_credentials(self) -> Dict[str, str]:
        """Get LLM service credentials from Vault.

        Returns:
            LLM credentials
        """
        if self.enabled:
            try:
                return self.client.get_secret(f"{self.secret_path}/llm")
            except Exception as e:
                logger.warning(f"Failed to get LLM credentials from Vault: {e}")

        # Fallback to environment variables
        return {
            "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
            "local_llm_api_key": os.getenv("LOCAL_LLM_API_KEY", ""),
        }

    def get_jwt_secret(self) -> str:
        """Get JWT secret from Vault.

        Returns:
            JWT secret key
        """
        if self.enabled:
            try:
                secret = self.client.get_secret(f"{self.secret_path}/jwt")
                return secret.get("secret_key", "")
            except Exception as e:
                logger.warning(f"Failed to get JWT secret from Vault: {e}")

        # Fallback to environment variable
        return os.getenv("SECRET_KEY", "your-secret-key-change-in-production")

    def store_secret(self, key: str, value: Dict[str, Any]) -> bool:
        """Store a secret in Vault.

        Args:
            key: Secret key
            value: Secret value

        Returns:
            True if successful
        """
        try:
            return self.client.put_secret(f"{self.secret_path}/{key}", value)
        except Exception as e:
            logger.error(f"Failed to store secret in Vault: {e}")
            return False

    def health_check(self) -> Dict[str, Any]:
        """Check Vault health.

        Returns:
            Health status
        """
        try:
            is_healthy = self.client.is_healthy()
            return {
                "status": "healthy" if is_healthy else "unhealthy",
                "enabled": self.enabled,
                "client_type": type(self.client).__name__,
            }
        except Exception as e:
            return {"status": "error", "enabled": self.enabled, "error": str(e)}


# Global Vault manager instance
vault_manager = VaultManager(
    enabled=os.getenv("VAULT_ENABLED", "false").lower() == "true",
    url=os.getenv("VAULT_URL"),
    token=os.getenv("VAULT_TOKEN"),
    mount_point=os.getenv("VAULT_MOUNT_POINT", "secret"),
    secret_path=os.getenv("VAULT_SECRET_PATH", "acp"),
)
