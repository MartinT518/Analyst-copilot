"""OAuth2/OIDC authentication implementation."""

import httpx
import jwt
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import structlog

from ..security_config import SecurityConfig

logger = structlog.get_logger(__name__)
security = HTTPBearer()


class OAuth2Service:
    """OAuth2/OIDC authentication service."""

    def __init__(self, config: SecurityConfig):
        """Initialize OAuth2 service."""
        self.config = config
        self.client = httpx.AsyncClient(timeout=30.0)
        self.logger = logger.bind(service="oauth2")

    async def get_authorization_url(self, state: str) -> str:
        """Generate OAuth2 authorization URL.

        Args:
            state: CSRF protection state parameter

        Returns:
            Authorization URL
        """
        params = {
            "client_id": self.config.oauth2_client_id,
            "response_type": "code",
            "redirect_uri": self.config.oauth2_redirect_uri,
            "scope": "openid profile email",
            "state": state,
        }

        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.config.oauth2_authorization_url}?{query_string}"

    async def exchange_code_for_token(self, code: str, state: str) -> Dict[str, Any]:
        """Exchange authorization code for access token.

        Args:
            code: Authorization code from OAuth2 provider
            state: CSRF protection state parameter

        Returns:
            Token response with access token and user info
        """
        try:
            # Exchange code for token
            token_data = {
                "grant_type": "authorization_code",
                "client_id": self.config.oauth2_client_id,
                "client_secret": self.config.oauth2_client_secret,
                "code": code,
                "redirect_uri": self.config.oauth2_redirect_uri,
            }

            response = await self.client.post(
                self.config.oauth2_token_url,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()

            token_response = response.json()
            access_token = token_response.get("access_token")

            if not access_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No access token received from OAuth2 provider",
                )

            # Get user info
            user_info = await self.get_user_info(access_token)

            # Generate JWT token
            jwt_token = self.create_jwt_token(user_info)

            return {
                "access_token": jwt_token,
                "token_type": "bearer",
                "expires_in": self.config.jwt_access_token_expire_minutes * 60,
                "user_info": user_info,
            }

        except httpx.HTTPError as e:
            self.logger.error("OAuth2 token exchange failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange authorization code for token",
            )

    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information from OAuth2 provider.

        Args:
            access_token: OAuth2 access token

        Returns:
            User information
        """
        try:
            response = await self.client.get(
                self.config.oauth2_userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()

            user_info = response.json()

            # Validate required fields
            required_fields = ["sub", "email"]
            for field in required_fields:
                if field not in user_info:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Missing required user field: {field}",
                    )

            return user_info

        except httpx.HTTPError as e:
            self.logger.error("Failed to get user info", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to retrieve user information",
            )

    def create_jwt_token(self, user_info: Dict[str, Any]) -> str:
        """Create JWT token for authenticated user.

        Args:
            user_info: User information from OAuth2 provider

        Returns:
            JWT token
        """
        now = datetime.utcnow()
        payload = {
            "sub": user_info["sub"],
            "email": user_info["email"],
            "name": user_info.get("name", ""),
            "iat": now,
            "exp": now + timedelta(minutes=self.config.jwt_access_token_expire_minutes),
            "iss": "acp-ingest",
            "aud": "acp-services",
        }

        return jwt.encode(
            payload, self.config.jwt_secret_key, algorithm=self.config.jwt_algorithm
        )

    def verify_jwt_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode JWT token.

        Args:
            token: JWT token to verify

        Returns:
            Decoded token payload
        """
        try:
            payload = jwt.decode(
                token,
                self.config.jwt_secret_key,
                algorithms=[self.config.jwt_algorithm],
                audience="acp-services",
                issuer="acp-ingest",
            )

            return payload

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}",
            )

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token.

        Args:
            refresh_token: Refresh token

        Returns:
            New token response
        """
        try:
            # Verify refresh token
            payload = self.verify_jwt_token(refresh_token)

            # Get fresh user info
            user_info = await self.get_user_info(payload.get("access_token", ""))

            # Create new JWT token
            jwt_token = self.create_jwt_token(user_info)

            return {
                "access_token": jwt_token,
                "token_type": "bearer",
                "expires_in": self.config.jwt_access_token_expire_minutes * 60,
            }

        except Exception as e:
            self.logger.error("Token refresh failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to refresh token",
            )

    async def revoke_token(self, token: str) -> bool:
        """Revoke access token.

        Args:
            token: Token to revoke

        Returns:
            True if successful
        """
        try:
            # In a real implementation, you would call the OAuth2 provider's
            # token revocation endpoint and maintain a blacklist
            self.logger.info("Token revoked", token_id=hash(token))
            return True

        except Exception as e:
            self.logger.error("Token revocation failed", error=str(e))
            return False


class AuthManager:
    """Authentication manager for dependency injection."""

    def __init__(self, config: SecurityConfig):
        """Initialize auth manager."""
        self.oauth2_service = OAuth2Service(config)
        self.config = config

    async def get_current_user(
        self, credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> Dict[str, Any]:
        """Get current authenticated user.

        Args:
            credentials: HTTP authorization credentials

        Returns:
            Current user information
        """
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
            )

        try:
            payload = self.oauth2_service.verify_jwt_token(credentials.credentials)
            return payload

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Authentication failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed"
            )

    async def get_current_active_user(
        self, current_user: Dict[str, Any] = Depends(get_current_user)
    ) -> Dict[str, Any]:
        """Get current active user (not disabled).

        Args:
            current_user: Current user from get_current_user

        Returns:
            Active user information
        """
        # In a real implementation, you would check if the user is active
        # For now, we assume all authenticated users are active
        return current_user

    def require_roles(self, required_roles: List[str]):
        """Create dependency that requires specific roles.

        Args:
            required_roles: List of required roles

        Returns:
            Dependency function
        """

        async def role_checker(
            current_user: Dict[str, Any] = Depends(self.get_current_active_user),
        ) -> Dict[str, Any]:
            user_roles = current_user.get("roles", [])

            if not any(role in user_roles for role in required_roles):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Required roles: {required_roles}",
                )

            return current_user

        return role_checker


def get_auth_manager(config: SecurityConfig) -> AuthManager:
    """Get authentication manager instance."""
    return AuthManager(config)
