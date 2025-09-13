"""Authentication related models."""

from typing import Optional

from pydantic import Field

from .common import BaseModel


class LoginRequest(BaseModel):
    """Login request model."""

    username: str = Field(..., description="Username", min_length=1)
    password: str = Field(..., description="Password", min_length=1)


class LoginResponse(BaseModel):
    """Login response model."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")


class LogoutResponse(BaseModel):
    """Logout response model."""

    message: str = Field(..., description="Logout confirmation message")


class AuthResponse(BaseModel):
    """Authentication response model."""

    id: Optional[str] = Field(None, description="User ID")
    username: str = Field(..., description="Username")
    role: str = Field(..., description="User role")
    auth_type: str = Field(..., description="Authentication type")
