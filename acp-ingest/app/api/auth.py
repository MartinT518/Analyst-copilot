"""Authentication API endpoints."""

import logging
from typing import Any

from acp_shared_models.auth import LoginRequest, LoginResponse, LogoutResponse
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.auth_service import auth_service, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()


class TokenRevocationRequest(BaseModel):
    """Token revocation request model."""

    token: str


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user and return access token.

    Args:
        request: Login credentials
        db: Database session

    Returns:
        LoginResponse: Access token and metadata

    Raises:
        HTTPException: If authentication fails
    """
    try:
        # Authenticate user
        user = auth_service.authenticate_user(request.username, request.password, db)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Create access token
        access_token = auth_service.create_access_token(
            data={"sub": user.username, "user_id": str(user.id), "role": user.role}
        )

        # Log successful login
        logger.info(f"User logged in: {user.username}")

        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=auth_service.settings.access_token_expire_minutes * 60,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error"
        )


@router.post("/logout", response_model=LogoutResponse)
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Logout user and revoke token.

    Args:
        credentials: Bearer token

    Returns:
        LogoutResponse: Logout confirmation

    Raises:
        HTTPException: If token revocation fails
    """
    try:
        # Revoke the token
        success = auth_service.revoke_token(credentials.credentials)

        if success:
            logger.info("User logged out successfully")
            return LogoutResponse(message="Logged out successfully")
        else:
            logger.warning("Token revocation failed")
            return LogoutResponse(message="Logged out (token revocation may have failed)")

    except Exception as e:
        logger.error(f"Logout failed: {e}")
        # Don't raise exception for logout failures - user is still logged out
        return LogoutResponse(message="Logged out (with warnings)")


@router.post("/revoke-token", response_model=dict[str, str])
async def revoke_token(
    request: TokenRevocationRequest, current_user: dict[str, Any] = Depends(get_current_user)
):
    """Revoke a specific token (admin function).

    Args:
        request: Token revocation request
        current_user: Current authenticated user

    Returns:
        Dict: Revocation result

    Raises:
        HTTPException: If revocation fails
    """
    try:
        # Check if user has admin privileges
        if current_user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
            )

        # Revoke the token
        success = auth_service.revoke_token(request.token)

        if success:
            logger.info(f"Token revoked by admin: {current_user.get('username')}")
            return {"message": "Token revoked successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to revoke token"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token revocation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error"
        )


@router.post("/revoke-user-tokens/{user_id}", response_model=dict[str, str])
async def revoke_user_tokens(
    user_id: str, current_user: dict[str, Any] = Depends(get_current_user)
):
    """Revoke all tokens for a specific user (admin function).

    Args:
        user_id: User ID to revoke tokens for
        current_user: Current authenticated user

    Returns:
        Dict: Revocation result

    Raises:
        HTTPException: If revocation fails
    """
    try:
        # Check if user has admin privileges or is revoking their own tokens
        if current_user.get("role") != "admin" and current_user.get("id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges or own user ID required",
            )

        # Revoke all tokens for user
        revoked_count = auth_service.revoke_all_user_tokens(user_id)

        logger.info(f"All tokens revoked for user {user_id} by {current_user.get('username')}")
        return {
            "message": f"All tokens revoked for user {user_id}",
            "tokens_revoked": str(revoked_count),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User token revocation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error"
        )


@router.get("/me", response_model=dict[str, Any])
async def get_current_user_info(current_user: dict[str, Any] = Depends(get_current_user)):
    """Get current user information.

    Args:
        current_user: Current authenticated user

    Returns:
        Dict: Current user information
    """
    return {
        "id": current_user.get("id"),
        "username": current_user.get("username"),
        "role": current_user.get("role"),
        "auth_type": current_user.get("auth_type"),
    }
