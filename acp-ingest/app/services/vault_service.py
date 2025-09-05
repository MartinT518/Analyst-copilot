"""HashiCorp Vault integration service for secrets management."""

import os
import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

import httpx
from app.config import get_settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()


class VaultService:
    """Service for managing secrets with HashiCorp Vault."""
    
    def __init__(self):
        self.vault_url = getattr(settings, 'VAULT_URL', 'http://localhost:8200')
        self.vault_token = getattr(settings, 'VAULT_TOKEN', None)
        self.vault_namespace = getattr(settings, 'VAULT_NAMESPACE', None)
        self.mount_point = getattr(settings, 'VAULT_MOUNT_POINT', 'secret')
        self.token_renewal_threshold = 300  # 5 minutes
        self._token_expires_at = None
        self._client = None
    
    async def initialize(self):
        """Initialize Vault service and authenticate."""
        logger.info("Initializing Vault service")
        
        try:
            # Create HTTP client
            self._client = httpx.AsyncClient(
                base_url=self.vault_url,
                timeout=30.0,
                headers=self._get_headers()
            )
            
            # Authenticate and get token info
            if self.vault_token:
                await self._validate_token()
            else:
                await self._authenticate()
            
            logger.info("Vault service initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize Vault service", error=str(e))
            raise
    
    async def cleanup(self):
        """Cleanup Vault service resources."""
        if self._client:
            await self._client.aclose()
            logger.info("Vault service cleaned up")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for Vault requests."""
        headers = {
            'Content-Type': 'application/json'
        }
        
        if self.vault_token:
            headers['X-Vault-Token'] = self.vault_token
        
        if self.vault_namespace:
            headers['X-Vault-Namespace'] = self.vault_namespace
        
        return headers
    
    async def _validate_token(self):
        """Validate current Vault token."""
        try:
            response = await self._client.get('/v1/auth/token/lookup-self')
            
            if response.status_code == 200:
                token_info = response.json()
                
                # Check token expiration
                if 'ttl' in token_info['data']:
                    ttl = token_info['data']['ttl']
                    self._token_expires_at = datetime.utcnow() + timedelta(seconds=ttl)
                    
                    logger.info("Token validated", expires_in=f"{ttl}s")
                else:
                    logger.warning("Token has no TTL information")
            else:
                raise Exception(f"Token validation failed: {response.status_code}")
                
        except Exception as e:
            logger.error("Token validation failed", error=str(e))
            raise
    
    async def _authenticate(self):
        """Authenticate with Vault using configured method."""
        # This is a placeholder for various auth methods
        # In production, you would implement specific auth methods like:
        # - AppRole authentication
        # - Kubernetes authentication
        # - AWS IAM authentication
        # - etc.
        
        auth_method = getattr(settings, 'VAULT_AUTH_METHOD', 'token')
        
        if auth_method == 'approle':
            await self._authenticate_approle()
        elif auth_method == 'kubernetes':
            await self._authenticate_kubernetes()
        else:
            raise Exception(f"Unsupported auth method: {auth_method}")
    
    async def _authenticate_approle(self):
        """Authenticate using AppRole method."""
        role_id = getattr(settings, 'VAULT_ROLE_ID', None)
        secret_id = getattr(settings, 'VAULT_SECRET_ID', None)
        
        if not role_id or not secret_id:
            raise Exception("AppRole authentication requires VAULT_ROLE_ID and VAULT_SECRET_ID")
        
        try:
            response = await self._client.post(
                '/v1/auth/approle/login',
                json={
                    'role_id': role_id,
                    'secret_id': secret_id
                }
            )
            
            if response.status_code == 200:
                auth_data = response.json()
                self.vault_token = auth_data['auth']['client_token']
                
                # Update headers with new token
                self._client.headers.update({'X-Vault-Token': self.vault_token})
                
                # Set token expiration
                lease_duration = auth_data['auth']['lease_duration']
                self._token_expires_at = datetime.utcnow() + timedelta(seconds=lease_duration)
                
                logger.info("AppRole authentication successful")
            else:
                raise Exception(f"AppRole authentication failed: {response.status_code}")
                
        except Exception as e:
            logger.error("AppRole authentication failed", error=str(e))
            raise
    
    async def _authenticate_kubernetes(self):
        """Authenticate using Kubernetes service account."""
        # Read service account token
        token_path = '/var/run/secrets/kubernetes.io/serviceaccount/token'
        
        if not os.path.exists(token_path):
            raise Exception("Kubernetes service account token not found")
        
        with open(token_path, 'r') as f:
            jwt_token = f.read().strip()
        
        role = getattr(settings, 'VAULT_K8S_ROLE', 'acp-ingest')
        
        try:
            response = await self._client.post(
                '/v1/auth/kubernetes/login',
                json={
                    'role': role,
                    'jwt': jwt_token
                }
            )
            
            if response.status_code == 200:
                auth_data = response.json()
                self.vault_token = auth_data['auth']['client_token']
                
                # Update headers with new token
                self._client.headers.update({'X-Vault-Token': self.vault_token})
                
                # Set token expiration
                lease_duration = auth_data['auth']['lease_duration']
                self._token_expires_at = datetime.utcnow() + timedelta(seconds=lease_duration)
                
                logger.info("Kubernetes authentication successful")
            else:
                raise Exception(f"Kubernetes authentication failed: {response.status_code}")
                
        except Exception as e:
            logger.error("Kubernetes authentication failed", error=str(e))
            raise
    
    async def _ensure_token_valid(self):
        """Ensure token is valid and renew if necessary."""
        if not self._token_expires_at:
            return
        
        time_until_expiry = (self._token_expires_at - datetime.utcnow()).total_seconds()
        
        if time_until_expiry < self.token_renewal_threshold:
            logger.info("Token expiring soon, attempting renewal")
            await self._renew_token()
    
    async def _renew_token(self):
        """Renew the current Vault token."""
        try:
            response = await self._client.post('/v1/auth/token/renew-self')
            
            if response.status_code == 200:
                token_info = response.json()
                lease_duration = token_info['auth']['lease_duration']
                self._token_expires_at = datetime.utcnow() + timedelta(seconds=lease_duration)
                
                logger.info("Token renewed successfully", new_ttl=f"{lease_duration}s")
            else:
                logger.warning("Token renewal failed, re-authenticating")
                await self._authenticate()
                
        except Exception as e:
            logger.error("Token renewal failed", error=str(e))
            # Try to re-authenticate
            await self._authenticate()
    
    async def get_secret(self, path: str, version: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve a secret from Vault.
        
        Args:
            path: Secret path
            version: Specific version to retrieve (for versioned secrets)
            
        Returns:
            Optional[Dict[str, Any]]: Secret data or None if not found
        """
        await self._ensure_token_valid()
        
        try:
            # Construct the full path
            if self.mount_point == 'secret':
                # KV v2 engine
                full_path = f'/v1/{self.mount_point}/data/{path}'
                params = {'version': version} if version else None
            else:
                # KV v1 or other engine
                full_path = f'/v1/{self.mount_point}/{path}'
                params = None
            
            response = await self._client.get(full_path, params=params)
            
            if response.status_code == 200:
                secret_data = response.json()
                
                # Handle KV v2 response format
                if 'data' in secret_data and 'data' in secret_data['data']:
                    return secret_data['data']['data']
                elif 'data' in secret_data:
                    return secret_data['data']
                else:
                    return secret_data
                    
            elif response.status_code == 404:
                logger.warning("Secret not found", path=path)
                return None
            else:
                logger.error("Failed to retrieve secret", path=path, status=response.status_code)
                return None
                
        except Exception as e:
            logger.error("Error retrieving secret", path=path, error=str(e))
            return None
    
    async def put_secret(self, path: str, data: Dict[str, Any]) -> bool:
        """
        Store a secret in Vault.
        
        Args:
            path: Secret path
            data: Secret data to store
            
        Returns:
            bool: True if successful
        """
        await self._ensure_token_valid()
        
        try:
            # Construct the full path
            if self.mount_point == 'secret':
                # KV v2 engine
                full_path = f'/v1/{self.mount_point}/data/{path}'
                payload = {'data': data}
            else:
                # KV v1 or other engine
                full_path = f'/v1/{self.mount_point}/{path}'
                payload = data
            
            response = await self._client.post(full_path, json=payload)
            
            if response.status_code in [200, 204]:
                logger.info("Secret stored successfully", path=path)
                return True
            else:
                logger.error("Failed to store secret", path=path, status=response.status_code)
                return False
                
        except Exception as e:
            logger.error("Error storing secret", path=path, error=str(e))
            return False
    
    async def delete_secret(self, path: str) -> bool:
        """
        Delete a secret from Vault.
        
        Args:
            path: Secret path
            
        Returns:
            bool: True if successful
        """
        await self._ensure_token_valid()
        
        try:
            # Construct the full path
            if self.mount_point == 'secret':
                # KV v2 engine - this marks the secret as deleted
                full_path = f'/v1/{self.mount_point}/data/{path}'
            else:
                # KV v1 or other engine
                full_path = f'/v1/{self.mount_point}/{path}'
            
            response = await self._client.delete(full_path)
            
            if response.status_code in [200, 204]:
                logger.info("Secret deleted successfully", path=path)
                return True
            else:
                logger.error("Failed to delete secret", path=path, status=response.status_code)
                return False
                
        except Exception as e:
            logger.error("Error deleting secret", path=path, error=str(e))
            return False
    
    async def list_secrets(self, path: str = "") -> List[str]:
        """
        List secrets at a given path.
        
        Args:
            path: Path to list
            
        Returns:
            List[str]: List of secret names
        """
        await self._ensure_token_valid()
        
        try:
            # Construct the full path
            if self.mount_point == 'secret':
                # KV v2 engine
                full_path = f'/v1/{self.mount_point}/metadata/{path}'
            else:
                # KV v1 or other engine
                full_path = f'/v1/{self.mount_point}/{path}'
            
            response = await self._client.request('LIST', full_path)
            
            if response.status_code == 200:
                list_data = response.json()
                return list_data.get('data', {}).get('keys', [])
            else:
                logger.error("Failed to list secrets", path=path, status=response.status_code)
                return []
                
        except Exception as e:
            logger.error("Error listing secrets", path=path, error=str(e))
            return []
    
    async def health_check(self) -> Dict[str, str]:
        """
        Check Vault service health.
        
        Returns:
            Dict[str, str]: Health status
        """
        try:
            if not self._client:
                return {"status": "unhealthy", "error": "Client not initialized"}
            
            response = await self._client.get('/v1/sys/health')
            
            if response.status_code == 200:
                health_data = response.json()
                
                if health_data.get('sealed', True):
                    return {"status": "unhealthy", "error": "Vault is sealed"}
                else:
                    return {"status": "healthy", "version": health_data.get('version', 'unknown')}
            else:
                return {"status": "unhealthy", "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


# Global Vault service instance
vault_service = VaultService()


async def get_vault_secret(path: str, version: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Convenience function to get a secret from Vault.
    
    Args:
        path: Secret path
        version: Specific version to retrieve
        
    Returns:
        Optional[Dict[str, Any]]: Secret data or None if not found
    """
    return await vault_service.get_secret(path, version)


async def put_vault_secret(path: str, data: Dict[str, Any]) -> bool:
    """
    Convenience function to store a secret in Vault.
    
    Args:
        path: Secret path
        data: Secret data to store
        
    Returns:
        bool: True if successful
    """
    return await vault_service.put_secret(path, data)

