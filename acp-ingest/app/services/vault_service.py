"""HashiCorp Vault integration for secrets management."""

import os
import logging
from typing import Optional, Dict, Any
import hvac
from hvac.exceptions import VaultError

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class VaultService:
    """Service for managing secrets with HashiCorp Vault."""

    def __init__(self):
        """Initialize Vault service."""
        self.client = None
        self.authenticated = False
        self.settings = settings

    async def initialize(self) -> bool:
        """Initialize Vault connection and authentication.

        Returns:
            bool: True if successfully initialized, False otherwise
        """
        if not self.settings.vault_url:
            logger.info("Vault URL not configured, skipping Vault initialization")
            return False

        try:
            # Create Vault client
            self.client = hvac.Client(url=self.settings.vault_url)

            # Set namespace if configured
            if self.settings.vault_namespace:
                self.client.adapter.namespace = self.settings.vault_namespace

            # Authenticate based on method
            if self.settings.vault_auth_method == "token":
                await self._authenticate_with_token()
            elif self.settings.vault_auth_method == "approle":
                await self._authenticate_with_approle()
            elif self.settings.vault_auth_method == "kubernetes":
                await self._authenticate_with_kubernetes()
            else:
                logger.error(
                    f"Unsupported Vault auth method: {self.settings.vault_auth_method}"
                )
                return False

            # Test connection
            if self.client.is_authenticated():
                self.authenticated = True
                logger.info("Successfully authenticated with Vault")
                return True
            else:
                logger.error("Failed to authenticate with Vault")
                return False

        except Exception as e:
            logger.error(f"Failed to initialize Vault service: {e}")
            return False

    async def _authenticate_with_token(self):
        """Authenticate using token method."""
        if not self.settings.vault_token:
            raise ValueError("VAULT_TOKEN is required for token authentication")

        self.client.token = self.settings.vault_token

    async def _authenticate_with_approle(self):
        """Authenticate using AppRole method."""
        if not self.settings.vault_role_id or not self.settings.vault_secret_id:
            raise ValueError(
                "VAULT_ROLE_ID and VAULT_SECRET_ID are required for AppRole authentication"
            )

        response = self.client.auth.approle.login(
            role_id=self.settings.vault_role_id, secret_id=self.settings.vault_secret_id
        )
        self.client.token = response["auth"]["client_token"]

    async def _authenticate_with_kubernetes(self):
        """Authenticate using Kubernetes method."""
        # Read JWT token from service account
        jwt_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
        if not os.path.exists(jwt_path):
            raise ValueError("Kubernetes service account token not found")

        with open(jwt_path, "r") as f:
            jwt_token = f.read().strip()

        response = self.client.auth.kubernetes.login(
            role=self.settings.vault_k8s_role, jwt=jwt_token
        )
        self.client.token = response["auth"]["client_token"]

    async def get_secret(self, path: str, key: Optional[str] = None) -> Any:
        """Get secret from Vault.

        Args:
            path: Secret path in Vault
            key: Specific key within the secret (optional)

        Returns:
            Secret value or dictionary of secrets
        """
        if not self.authenticated:
            logger.warning("Vault not authenticated, cannot retrieve secret")
            return None

        try:
            # Read secret from KV v2 engine
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path, mount_point=self.settings.vault_mount_point
            )

            secret_data = response["data"]["data"]

            if key:
                return secret_data.get(key)
            else:
                return secret_data

        except VaultError as e:
            logger.error(f"Failed to read secret from Vault: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading secret from Vault: {e}")
            return None

    async def set_secret(self, path: str, data: Dict[str, Any]) -> bool:
        """Set secret in Vault.

        Args:
            path: Secret path in Vault
            data: Secret data to store

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.authenticated:
            logger.warning("Vault not authenticated, cannot set secret")
            return False

        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path, secret=data, mount_point=self.settings.vault_mount_point
            )
            logger.info(f"Successfully stored secret at path: {path}")
            return True

        except VaultError as e:
            logger.error(f"Failed to store secret in Vault: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error storing secret in Vault: {e}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Check Vault service health.

        Returns:
            Dict containing health status information
        """
        if not self.client:
            return {"healthy": False, "error": "Vault client not initialized"}

        try:
            # Check if Vault is sealed
            status = self.client.sys.read_health_status()

            return {
                "healthy": status.get("initialized", False)
                and not status.get("sealed", True),
                "initialized": status.get("initialized", False),
                "sealed": status.get("sealed", True),
                "version": status.get("version", "unknown"),
                "authenticated": self.authenticated,
            }

        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def cleanup(self):
        """Cleanup Vault service."""
        if self.client:
            # Revoke token if we have one
            try:
                if self.client.token:
                    self.client.auth.token.revoke_self()
            except Exception as e:
                logger.warning(f"Failed to revoke Vault token: {e}")

            self.client = None
            self.authenticated = False


# Global Vault service instance
vault_service = VaultService()


async def get_vault_secret(
    path: str, key: Optional[str] = None, fallback: Any = None
) -> Any:
    """Convenience function to get secrets from Vault with fallback.

    Args:
        path: Secret path in Vault
        key: Specific key within the secret
        fallback: Fallback value if secret not found

    Returns:
        Secret value or fallback
    """
    if not vault_service.authenticated:
        return fallback

    secret = await vault_service.get_secret(path, key)
    return secret if secret is not None else fallback
