"""Authentication service for user management and API key validation."""

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

import redis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import APIKey, AuditLog, User
from ..schemas import UserCreate

logger = logging.getLogger(__name__)
settings = get_settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
ALGORITHM = "HS256"

# Security scheme
security = HTTPBearer()


class AuthService:
    """Service for handling authentication and authorization."""

    def __init__(self):
        self.settings = settings
        # Initialize Redis client for JWT revocation list
        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            # Test connection
            self.redis_client.ping()
            logger.info("Redis client initialized for JWT revocation list")
        except Exception as e:
            logger.warning(f"Failed to initialize Redis client: {e}")
            self.redis_client = None

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)

    def create_access_token(
        self, data: dict[str, Any], expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT access token.

        Args:
            data: Data to encode in token
            expires_delta: Token expiration time

        Returns:
            str: JWT token
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

        # Add JWT ID for revocation tracking
        to_encode.update(
            {
                "exp": expire,
                "jti": str(uuid.uuid4()),
                "iat": datetime.utcnow(),
            }
        )
        encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
        return encoded_jwt

    def verify_token(self, token: str) -> Optional[dict[str, Any]]:
        """Verify and decode a JWT token.

        Args:
            token: JWT token

        Returns:
            Optional[Dict[str, Any]]: Decoded token data or None if invalid
        """
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])

            # Check if token is in revocation list
            if self._is_token_revoked(payload.get("jti")):
                return None

            return payload
        except JWTError:
            return None

    def revoke_token(self, token: str) -> bool:
        """Revoke a JWT token by adding it to the revocation list.

        Args:
            token: JWT token to revoke

        Returns:
            bool: True if token was successfully revoked
        """
        try:
            # Decode token to get JTI and expiration
            payload = jwt.decode(
                token, settings.secret_key, algorithms=[ALGORITHM], options={"verify_exp": False}
            )
            jti = payload.get("jti")
            exp = payload.get("exp")

            if not jti or not exp:
                return False

            if self.redis_client is None:
                logger.warning("Redis client not available, cannot revoke token")
                return False

            # Calculate TTL (time to live) until token expires
            exp_datetime = datetime.utcfromtimestamp(exp)
            ttl_seconds = int((exp_datetime - datetime.utcnow()).total_seconds())

            if ttl_seconds > 0:
                # Store token JTI in Redis with TTL matching token expiration
                self.redis_client.setex(f"revoked_token:{jti}", ttl_seconds, "revoked")
                logger.info(f"Token revoked: {jti}")
                return True
            else:
                # Token already expired
                logger.info(f"Token already expired: {jti}")
                return True

        except Exception as e:
            logger.error(f"Failed to revoke token: {e}")
            return False

    def _is_token_revoked(self, jti: str) -> bool:
        """Check if a token JTI is in the revocation list.

        Args:
            jti: JWT ID to check

        Returns:
            bool: True if token is revoked
        """
        if not jti or self.redis_client is None:
            return False

        try:
            return self.redis_client.exists(f"revoked_token:{jti}") > 0
        except Exception as e:
            logger.error(f"Failed to check token revocation status: {e}")
            return False

    def revoke_all_user_tokens(self, user_id: str) -> int:
        """Revoke all tokens for a specific user by storing user ID in revocation list.

        Args:
            user_id: User ID to revoke all tokens for

        Returns:
            int: Number of tokens potentially revoked
        """
        if self.redis_client is None:
            logger.warning("Redis client not available, cannot revoke user tokens")
            return 0

        try:
            # Store user ID in revocation list with a reasonable TTL
            # This is a simple approach - in production you might want to track individual tokens
            ttl_seconds = settings.access_token_expire_minutes * 60  # Convert to seconds
            self.redis_client.setex(f"revoked_user:{user_id}", ttl_seconds, "revoked")
            logger.info(f"All tokens revoked for user: {user_id}")
            return 1  # Return 1 as we can't count individual tokens with this approach
        except Exception as e:
            logger.error(f"Failed to revoke user tokens: {e}")
            return 0

    def authenticate_user(self, username: str, password: str, db: Session) -> Optional[User]:
        """Authenticate a user with username and password.

        Args:
            username: Username
            password: Password
            db: Database session

        Returns:
            Optional[User]: User object if authenticated, None otherwise
        """
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        return user

    def create_user(self, user_data: UserCreate, db: Session) -> User:
        """Create a new user.

        Args:
            user_data: User creation data
            db: Database session

        Returns:
            User: Created user
        """
        # Check if username or email already exists
        existing_user = (
            db.query(User)
            .filter((User.username == user_data.username) | (User.email == user_data.email))
            .first()
        )

        if existing_user:
            raise HTTPException(status_code=400, detail="Username or email already registered")

        # Create new user
        hashed_password = self.get_password_hash(user_data.password)
        user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password,
            role=user_data.role.value,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        logger.info(f"Created user: {user.username}")
        return user

    def generate_api_key(self) -> tuple[str, str]:
        """Generate a new API key.

        Returns:
            tuple[str, str]: (api_key, api_key_hash)
        """
        api_key = f"acp_{secrets.token_urlsafe(32)}"
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        return api_key, api_key_hash

    def create_api_key(
        self,
        name: str,
        user_id: str,
        permissions: list[str],
        expires_in_days: Optional[int],
        db: Session,
    ) -> tuple[APIKey, str]:
        """Create a new API key.

        Args:
            name: API key name
            user_id: User ID
            permissions: List of permissions
            expires_in_days: Expiration in days
            db: Database session

        Returns:
            tuple[APIKey, str]: (API key record, actual key)
        """
        api_key, api_key_hash = self.generate_api_key()

        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        api_key_record = APIKey(
            name=name,
            key_hash=api_key_hash,
            user_id=user_id,
            permissions=permissions,
            expires_at=expires_at,
        )

        db.add(api_key_record)
        db.commit()
        db.refresh(api_key_record)

        logger.info(f"Created API key: {name} for user {user_id}")
        return api_key_record, api_key

    def validate_api_key(self, api_key: str, db: Session) -> Optional[APIKey]:
        """Validate an API key.

        Args:
            api_key: API key to validate
            db: Database session

        Returns:
            Optional[APIKey]: API key record if valid, None otherwise
        """
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        api_key_record = (
            db.query(APIKey)
            .filter(APIKey.key_hash == api_key_hash, APIKey.is_active == True)
            .first()
        )

        if not api_key_record:
            return None

        # Check expiration
        if api_key_record.expires_at and api_key_record.expires_at < datetime.utcnow():
            return None

        # Update last used timestamp
        api_key_record.last_used = datetime.utcnow()
        db.commit()

        return api_key_record

    async def get_current_user(
        self,
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Get current authenticated user from token or API key.

        Args:
            credentials: HTTP authorization credentials
            db: Database session

        Returns:
            Dict[str, Any]: User information
        """
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

        token = credentials.credentials

        # Try JWT token first
        payload = self.verify_token(token)
        if payload:
            username = payload.get("sub")
            if username is None:
                raise credentials_exception

            user = db.query(User).filter(User.username == username).first()
            if user is None:
                raise credentials_exception

            return {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "auth_type": "jwt",
            }

        # Try API key
        api_key_record = self.validate_api_key(token, db)
        if api_key_record:
            user = db.query(User).filter(User.id == api_key_record.user_id).first()
            if user is None:
                raise credentials_exception

            return {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "auth_type": "api_key",
                "api_key_id": str(api_key_record.id),
                "permissions": api_key_record.permissions,
            }

        raise credentials_exception

    def require_role(self, required_role: str):
        """Dependency to require a specific role.

        Args:
            required_role: Required user role
        """

        def role_checker(current_user: dict[str, Any] = Depends(self.get_current_user)):
            role_hierarchy = {"analyst": 1, "reviewer": 2, "admin": 3}

            user_role_level = role_hierarchy.get(current_user["role"], 0)
            required_role_level = role_hierarchy.get(required_role, 999)

            if user_role_level < required_role_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions",
                )

            return current_user

        return role_checker

    def require_permission(self, required_permission: str):
        """Dependency to require a specific permission (for API keys).

        Args:
            required_permission: Required permission
        """

        def permission_checker(
            current_user: dict[str, Any] = Depends(self.get_current_user),
        ):
            # JWT tokens have full permissions based on role
            if current_user.get("auth_type") == "jwt":
                return current_user

            # Check API key permissions
            permissions = current_user.get("permissions", [])
            if required_permission not in permissions and "all" not in permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission '{required_permission}' required",
                )

            return current_user

        return permission_checker

    def log_auth_event(
        self,
        action: str,
        user_id: str,
        details: dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        db: Session = None,
    ):
        """Log authentication events.

        Args:
            action: Authentication action
            user_id: User ID
            details: Event details
            ip_address: Client IP address
            user_agent: Client user agent
            db: Database session
        """
        try:
            audit_log = AuditLog(
                action=action,
                user_id=user_id,
                resource_type="auth",
                details=details,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            db.add(audit_log)
            db.commit()

        except Exception as e:
            logger.error(f"Failed to log auth event: {e}")

    def create_default_admin(self, db: Session) -> Optional[User]:
        """Create default admin user if no users exist.

        Args:
            db: Database session

        Returns:
            Optional[User]: Created admin user or None
        """
        # Check if any users exist
        user_count = db.query(User).count()
        if user_count > 0:
            return None

        # No users exist - admin should be created via bootstrap script
        logger.info("No users found. Use bootstrap script to create initial admin user.")
        return None


# Global auth service instance
auth_service = AuthService()


# Standalone function for FastAPI dependency injection
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get current authenticated user from token or API key.

    This is a standalone function for FastAPI dependency injection.
    """
    return await auth_service.get_current_user(credentials, db)
