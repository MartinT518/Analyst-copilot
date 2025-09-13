"""Security utilities for rate limiting, headers, and input validation."""

import hashlib
import secrets
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, List, Optional, Union

import bleach
import redis
from fastapi import HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, validator
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimiter:
    """Redis-based rate limiter."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def is_allowed(
        self, key: str, limit: int, window: int, identifier: str = None
    ) -> tuple[bool, Dict[str, Any]]:
        """
        Check if request is allowed based on rate limit.

        Args:
            key: Rate limit key (e.g., 'api_calls')
            limit: Maximum number of requests
            window: Time window in seconds
            identifier: Unique identifier (IP, user ID, etc.)

        Returns:
            Tuple of (is_allowed, info_dict)
        """
        if identifier:
            rate_key = f"rate_limit:{key}:{identifier}"
        else:
            rate_key = f"rate_limit:{key}"

        current_time = int(time.time())
        window_start = current_time - window

        # Use sliding window log
        pipe = self.redis.pipeline()

        # Remove old entries
        pipe.zremrangebyscore(rate_key, 0, window_start)

        # Count current requests
        pipe.zcard(rate_key)

        # Add current request
        pipe.zadd(rate_key, {str(current_time): current_time})

        # Set expiration
        pipe.expire(rate_key, window)

        results = pipe.execute()
        current_requests = results[1]

        is_allowed = current_requests < limit

        info = {
            "limit": limit,
            "remaining": max(0, limit - current_requests - 1),
            "reset_time": current_time + window,
            "retry_after": window if not is_allowed else None,
        }

        return is_allowed, info

    def get_rate_limit_info(self, key: str, identifier: str = None) -> Dict[str, Any]:
        """Get current rate limit information."""
        if identifier:
            rate_key = f"rate_limit:{key}:{identifier}"
        else:
            rate_key = f"rate_limit:{key}"

        current_requests = self.redis.zcard(rate_key)
        ttl = self.redis.ttl(rate_key)

        return {"current_requests": current_requests, "ttl": ttl}


class SecurityHeaders:
    """Security headers configuration."""

    DEFAULT_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    }

    @classmethod
    def get_headers(cls, custom_headers: Dict[str, str] = None) -> Dict[str, str]:
        """Get security headers with optional custom headers."""
        headers = cls.DEFAULT_HEADERS.copy()
        if custom_headers:
            headers.update(custom_headers)
        return headers


class InputValidator:
    """Input validation and sanitization utilities."""

    # Allowed HTML tags for rich text content
    ALLOWED_TAGS = [
        "p",
        "br",
        "strong",
        "em",
        "u",
        "ol",
        "ul",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "blockquote",
        "code",
        "pre",
        "a",
        "img",
    ]

    ALLOWED_ATTRIBUTES = {
        "a": ["href", "title"],
        "img": ["src", "alt", "title", "width", "height"],
        "*": ["class"],
    }

    @classmethod
    def sanitize_html(cls, content: str) -> str:
        """Sanitize HTML content."""
        return bleach.clean(
            content, tags=cls.ALLOWED_TAGS, attributes=cls.ALLOWED_ATTRIBUTES, strip=True
        )

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """Sanitize filename to prevent path traversal."""
        # Remove path separators and dangerous characters
        dangerous_chars = ["/", "\\", "..", "<", ">", ":", '"', "|", "?", "*"]
        sanitized = filename

        for char in dangerous_chars:
            sanitized = sanitized.replace(char, "_")

        # Limit length
        if len(sanitized) > 255:
            name, ext = sanitized.rsplit(".", 1) if "." in sanitized else (sanitized, "")
            sanitized = name[:250] + ("." + ext if ext else "")

        return sanitized

    @classmethod
    def validate_email(cls, email: str) -> bool:
        """Basic email validation."""
        import re

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    @classmethod
    def validate_url(cls, url: str) -> bool:
        """Basic URL validation."""
        import re

        pattern = r"^https?://[^\s/$.?#].[^\s]*$"
        return bool(re.match(pattern, url))


class APIKeyValidator:
    """API key validation utilities."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def generate_api_key(self, user_id: str, name: str = None) -> str:
        """Generate a new API key."""
        # Generate secure random key
        key = secrets.token_urlsafe(32)

        # Store key metadata
        key_data = {
            "user_id": user_id,
            "name": name or "Default",
            "created_at": datetime.utcnow().isoformat(),
            "last_used": None,
            "is_active": True,
        }

        self.redis.hset(f"api_key:{key}", mapping=key_data)

        # Add to user's key list
        self.redis.sadd(f"user_keys:{user_id}", key)

        return key

    def validate_api_key(self, key: str) -> Optional[Dict[str, Any]]:
        """Validate API key and return user info."""
        key_data = self.redis.hgetall(f"api_key:{key}")

        if not key_data:
            return None

        # Convert bytes to strings
        key_info = {k.decode(): v.decode() for k, v in key_data.items()}

        # Check if key is active
        if not key_info.get("is_active", "").lower() == "true":
            return None

        # Update last used timestamp
        self.redis.hset(f"api_key:{key}", "last_used", datetime.utcnow().isoformat())

        return key_info

    def revoke_api_key(self, key: str) -> bool:
        """Revoke an API key."""
        key_data = self.redis.hgetall(f"api_key:{key}")

        if not key_data:
            return False

        user_id = key_data.get(b"user_id", b"").decode()

        # Mark as inactive
        self.redis.hset(f"api_key:{key}", "is_active", "false")

        # Remove from user's active keys
        self.redis.srem(f"user_keys:{user_id}", key)

        return True


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for FastAPI."""

    def __init__(
        self,
        app,
        rate_limiter: RateLimiter = None,
        api_key_validator: APIKeyValidator = None,
        enable_rate_limiting: bool = True,
        enable_security_headers: bool = True,
        rate_limit_config: Dict[str, Dict[str, int]] = None,
    ):
        super().__init__(app)
        self.rate_limiter = rate_limiter
        self.api_key_validator = api_key_validator
        self.enable_rate_limiting = enable_rate_limiting
        self.enable_security_headers = enable_security_headers

        # Default rate limit configuration
        self.rate_limit_config = rate_limit_config or {
            "default": {"limit": 100, "window": 60},  # 100 requests per minute
            "auth": {"limit": 10, "window": 60},  # 10 auth requests per minute
            "upload": {"limit": 5, "window": 60},  # 5 uploads per minute
        }

    async def dispatch(self, request: Request, call_next):
        # Get client identifier
        client_ip = request.client.host
        user_agent = request.headers.get("user-agent", "")
        identifier = hashlib.md5(f"{client_ip}:{user_agent}".encode()).hexdigest()

        # Rate limiting
        if self.enable_rate_limiting and self.rate_limiter:
            # Determine rate limit category
            path = request.url.path
            if path.startswith("/auth"):
                category = "auth"
            elif path.startswith("/upload") or request.method == "POST":
                category = "upload"
            else:
                category = "default"

            config = self.rate_limit_config.get(category, self.rate_limit_config["default"])

            is_allowed, rate_info = self.rate_limiter.is_allowed(
                category, config["limit"], config["window"], identifier
            )

            if not is_allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "retry_after": rate_info["retry_after"],
                    },
                    headers={
                        "X-RateLimit-Limit": str(rate_info["limit"]),
                        "X-RateLimit-Remaining": str(rate_info["remaining"]),
                        "X-RateLimit-Reset": str(rate_info["reset_time"]),
                        "Retry-After": str(rate_info["retry_after"]),
                    },
                )

        # Process request
        response = await call_next(request)

        # Add security headers
        if self.enable_security_headers:
            security_headers = SecurityHeaders.get_headers()
            for header, value in security_headers.items():
                response.headers[header] = value

        # Add rate limit headers
        if self.enable_rate_limiting and self.rate_limiter:
            response.headers["X-RateLimit-Limit"] = str(rate_info["limit"])
            response.headers["X-RateLimit-Remaining"] = str(rate_info["remaining"])
            response.headers["X-RateLimit-Reset"] = str(rate_info["reset_time"])

        return response


class SecureAPIKeyBearer(HTTPBearer):
    """Secure API key bearer authentication."""

    def __init__(self, api_key_validator: APIKeyValidator):
        super().__init__()
        self.api_key_validator = api_key_validator

    async def __call__(self, request: Request) -> Optional[Dict[str, Any]]:
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)

        if not credentials:
            raise HTTPException(status_code=401, detail="Missing authentication credentials")

        if credentials.scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")

        # Validate API key
        key_info = self.api_key_validator.validate_api_key(credentials.credentials)

        if not key_info:
            raise HTTPException(status_code=401, detail="Invalid or expired API key")

        return key_info


def rate_limit(
    key: str, limit: int, window: int, rate_limiter: RateLimiter, identifier_func: callable = None
):
    """Decorator for rate limiting specific endpoints."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args/kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if not request:
                # If no request found, skip rate limiting
                return await func(*args, **kwargs)

            # Get identifier
            if identifier_func:
                identifier = identifier_func(request)
            else:
                client_ip = request.client.host
                user_agent = request.headers.get("user-agent", "")
                identifier = hashlib.md5(f"{client_ip}:{user_agent}".encode()).hexdigest()

            # Check rate limit
            is_allowed, rate_info = rate_limiter.is_allowed(key, limit, window, identifier)

            if not is_allowed:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers={
                        "X-RateLimit-Limit": str(rate_info["limit"]),
                        "X-RateLimit-Remaining": str(rate_info["remaining"]),
                        "X-RateLimit-Reset": str(rate_info["reset_time"]),
                        "Retry-After": str(rate_info["retry_after"]),
                    },
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


class SecureFileUpload:
    """Secure file upload utilities."""

    ALLOWED_EXTENSIONS = {
        "csv",
        "txt",
        "md",
        "html",
        "htm",
        "xml",
        "json",
        "pdf",
        "doc",
        "docx",
        "odt",
        "rtf",
        "zip",
        "tar",
        "gz",
    }

    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

    @classmethod
    def validate_file(cls, filename: str, content: bytes) -> Dict[str, Any]:
        """Validate uploaded file."""
        errors = []

        # Check filename
        if not filename:
            errors.append("Filename is required")
        else:
            # Check extension
            ext = filename.lower().split(".")[-1] if "." in filename else ""
            if ext not in cls.ALLOWED_EXTENSIONS:
                errors.append(f"File type '{ext}' not allowed")

        # Check file size
        if len(content) > cls.MAX_FILE_SIZE:
            errors.append(f"File size exceeds maximum of {cls.MAX_FILE_SIZE // (1024*1024)}MB")

        # Basic content validation
        if len(content) == 0:
            errors.append("File is empty")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "size": len(content),
            "extension": ext if filename else None,
        }

    @classmethod
    def scan_for_malware(cls, content: bytes) -> Dict[str, Any]:
        """Basic malware scanning (placeholder for real implementation)."""
        # In production, integrate with ClamAV or similar
        suspicious_patterns = [b"<script", b"javascript:", b"vbscript:", b"onload=", b"onerror="]

        threats_found = []
        for pattern in suspicious_patterns:
            if pattern in content.lower():
                threats_found.append(f"Suspicious pattern: {pattern.decode()}")

        return {"clean": len(threats_found) == 0, "threats": threats_found}
