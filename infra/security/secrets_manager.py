"""Secrets manager for secure configuration and credential management."""

import os
import json
import base64
from typing import Dict, Any, Optional, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

from ..vault.vault_client import vault_manager

logger = logging.getLogger(__name__)


class SecretsManager:
    """Manager for handling secrets and sensitive configuration."""
    
    def __init__(self, encryption_key: Optional[str] = None):
        """Initialize secrets manager.
        
        Args:
            encryption_key: Optional encryption key for local secrets
        """
        self.vault = vault_manager
        self._encryption_key = encryption_key
        self._fernet = None
        
        if encryption_key:
            self._setup_encryption(encryption_key)
    
    def _setup_encryption(self, password: str) -> None:
        """Set up encryption for local secrets.
        
        Args:
            password: Password for encryption
        """
        try:
            # Generate key from password
            password_bytes = password.encode()
            salt = b'acp_salt_2024'  # In production, use a random salt
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
            self._fernet = Fernet(key)
        except Exception as e:
            logger.error(f"Failed to setup encryption: {e}")
    
    def encrypt_value(self, value: str) -> str:
        """Encrypt a value.
        
        Args:
            value: Value to encrypt
            
        Returns:
            Encrypted value
        """
        if not self._fernet:
            return value
        
        try:
            encrypted = self._fernet.encrypt(value.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Failed to encrypt value: {e}")
            return value
    
    def decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt a value.
        
        Args:
            encrypted_value: Encrypted value
            
        Returns:
            Decrypted value
        """
        if not self._fernet:
            return encrypted_value
        
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_value.encode())
            decrypted = self._fernet.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt value: {e}")
            return encrypted_value
    
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a secret value.
        
        Args:
            key: Secret key
            default: Default value if not found
            
        Returns:
            Secret value
        """
        # Try Vault first
        if self.vault.enabled:
            try:
                vault_secrets = self.vault.client.get_secret("acp/secrets")
                if key in vault_secrets:
                    return vault_secrets[key]
            except Exception as e:
                logger.debug(f"Failed to get secret from Vault: {e}")
        
        # Try environment variable
        env_value = os.getenv(key.upper())
        if env_value:
            # Check if value is encrypted
            if env_value.startswith("ENC:"):
                return self.decrypt_value(env_value[4:])
            return env_value
        
        return default
    
    def set_secret(self, key: str, value: str, encrypt: bool = False) -> bool:
        """Set a secret value.
        
        Args:
            key: Secret key
            value: Secret value
            encrypt: Whether to encrypt the value
            
        Returns:
            True if successful
        """
        # Store in Vault if enabled
        if self.vault.enabled:
            try:
                return self.vault.store_secret("secrets", {key: value})
            except Exception as e:
                logger.error(f"Failed to store secret in Vault: {e}")
        
        # Store as environment variable (for development)
        if encrypt and self._fernet:
            value = "ENC:" + self.encrypt_value(value)
        
        os.environ[key.upper()] = value
        return True
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration.
        
        Returns:
            Database configuration
        """
        if self.vault.enabled:
            try:
                return self.vault.get_database_credentials()
            except Exception as e:
                logger.warning(f"Failed to get database config from Vault: {e}")
        
        return {
            "host": self.get_secret("DATABASE_HOST", "localhost"),
            "port": int(self.get_secret("DATABASE_PORT", "5432")),
            "name": self.get_secret("DATABASE_NAME", "acp_db"),
            "user": self.get_secret("DATABASE_USER", "acp_user"),
            "password": self.get_secret("DATABASE_PASSWORD", "acp_password")
        }
    
    def get_redis_config(self) -> Dict[str, Any]:
        """Get Redis configuration.
        
        Returns:
            Redis configuration
        """
        if self.vault.enabled:
            try:
                return self.vault.get_redis_credentials()
            except Exception as e:
                logger.warning(f"Failed to get Redis config from Vault: {e}")
        
        return {
            "host": self.get_secret("REDIS_HOST", "localhost"),
            "port": int(self.get_secret("REDIS_PORT", "6379")),
            "db": int(self.get_secret("REDIS_DB", "0")),
            "password": self.get_secret("REDIS_PASSWORD", "")
        }
    
    def get_llm_config(self) -> Dict[str, Any]:
        """Get LLM configuration.
        
        Returns:
            LLM configuration
        """
        if self.vault.enabled:
            try:
                return self.vault.get_llm_credentials()
            except Exception as e:
                logger.warning(f"Failed to get LLM config from Vault: {e}")
        
        return {
            "openai_api_key": self.get_secret("OPENAI_API_KEY", ""),
            "llm_endpoint": self.get_secret("LLM_ENDPOINT", "https://api.openai.com/v1"),
            "embedding_endpoint": self.get_secret("EMBEDDING_ENDPOINT", "https://api.openai.com/v1"),
            "local_llm_url": self.get_secret("LOCAL_LLM_URL", ""),
            "local_llm_api_key": self.get_secret("LOCAL_LLM_API_KEY", "")
        }
    
    def get_jwt_config(self) -> Dict[str, Any]:
        """Get JWT configuration.
        
        Returns:
            JWT configuration
        """
        secret_key = self.get_secret("SECRET_KEY")
        if not secret_key:
            if self.vault.enabled:
                secret_key = self.vault.get_jwt_secret()
            else:
                secret_key = "your-secret-key-change-in-production"
        
        return {
            "secret_key": secret_key,
            "algorithm": self.get_secret("JWT_ALGORITHM", "HS256"),
            "expire_minutes": int(self.get_secret("JWT_EXPIRE_MINUTES", "1440"))
        }
    
    def validate_secrets(self) -> Dict[str, Any]:
        """Validate that all required secrets are available.
        
        Returns:
            Validation results
        """
        required_secrets = [
            "SECRET_KEY",
            "DATABASE_PASSWORD",
            "OPENAI_API_KEY"
        ]
        
        missing_secrets = []
        weak_secrets = []
        
        for secret in required_secrets:
            value = self.get_secret(secret)
            if not value:
                missing_secrets.append(secret)
            elif secret == "SECRET_KEY" and len(value) < 32:
                weak_secrets.append(f"{secret} (too short)")
        
        return {
            "valid": len(missing_secrets) == 0 and len(weak_secrets) == 0,
            "missing_secrets": missing_secrets,
            "weak_secrets": weak_secrets,
            "vault_enabled": self.vault.enabled,
            "vault_healthy": self.vault.client.is_healthy() if self.vault.enabled else False
        }
    
    def rotate_secret(self, key: str) -> str:
        """Rotate a secret by generating a new value.
        
        Args:
            key: Secret key to rotate
            
        Returns:
            New secret value
        """
        import secrets
        import string
        
        # Generate new secret
        if key == "SECRET_KEY":
            new_value = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(64))
        elif key.endswith("_API_KEY"):
            new_value = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
        else:
            new_value = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
        
        # Store new secret
        self.set_secret(key, new_value)
        
        logger.info(f"Rotated secret: {key}")
        return new_value
    
    def export_secrets(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Export secrets configuration.
        
        Args:
            include_sensitive: Whether to include sensitive values
            
        Returns:
            Secrets configuration
        """
        config = {
            "vault_enabled": self.vault.enabled,
            "encryption_enabled": self._fernet is not None,
            "secrets_count": 0
        }
        
        if include_sensitive:
            config["database"] = self.get_database_config()
            config["redis"] = self.get_redis_config()
            config["llm"] = self.get_llm_config()
            config["jwt"] = self.get_jwt_config()
        else:
            # Only include non-sensitive configuration
            config["database"] = {
                "host": self.get_secret("DATABASE_HOST", "localhost"),
                "port": int(self.get_secret("DATABASE_PORT", "5432")),
                "name": self.get_secret("DATABASE_NAME", "acp_db")
            }
            config["redis"] = {
                "host": self.get_secret("REDIS_HOST", "localhost"),
                "port": int(self.get_secret("REDIS_PORT", "6379"))
            }
        
        return config


# Global secrets manager instance
secrets_manager = SecretsManager(
    encryption_key=os.getenv("SECRETS_ENCRYPTION_KEY")
)

