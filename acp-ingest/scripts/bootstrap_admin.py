#!/usr/bin/env python3
"""
Bootstrap script for creating initial admin user.

This script creates the first admin user with a strong random password.
It should be run once during initial setup and the password should be
changed immediately after first login.

Usage:
    python scripts/bootstrap_admin.py
"""

import os
import secrets
import string
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from app.config import get_settings
from app.database import get_db
from app.models import User, UserCreate
from app.services.auth_service import AuthService

logger = structlog.get_logger(__name__)


def generate_strong_password(length: int = 16) -> str:
    """Generate a strong random password.

    Args:
        length: Length of the password

    Returns:
        Strong random password
    """
    # Define character sets
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    special = "!@#$%^&*()_+-=[]{}|;:,.<>?"

    # Ensure at least one character from each set
    password = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(digits),
        secrets.choice(special),
    ]

    # Fill the rest with random characters
    all_chars = lowercase + uppercase + digits + special
    for _ in range(length - 4):
        password.append(secrets.choice(all_chars))

    # Shuffle the password
    secrets.SystemRandom().shuffle(password)

    return "".join(password)


def create_admin_user() -> tuple[str, str]:
    """Create the initial admin user.

    Returns:
        Tuple of (username, password)
    """
    settings = get_settings()
    auth_service = AuthService()

    # Check if any users already exist
    db = next(get_db())
    try:
        existing_users = db.query(User).count()
        if existing_users > 0:
            logger.warning(
                "Users already exist in the database. Skipping admin user creation."
            )
            return None, None

        # Generate strong password
        password = generate_strong_password()

        # Create admin user
        admin_data = UserCreate(
            username="admin",
            email=os.getenv("ADMIN_EMAIL", "admin@localhost"),
            password=password,
            role="admin",
        )

        admin_user = auth_service.create_user(admin_data, db)

        if admin_user:
            logger.info("Admin user created successfully", username=admin_user.username)
            return admin_user.username, password
        else:
            logger.error("Failed to create admin user")
            return None, None

    except Exception as e:
        logger.error("Error creating admin user", error=str(e))
        return None, None
    finally:
        db.close()


def main():
    """Main bootstrap function."""
    print("🔐 Analyst Copilot - Admin User Bootstrap")
    print("=" * 50)

    # Check if we're in the right environment
    if os.getenv("ENVIRONMENT") == "production":
        print("⚠️  WARNING: Running in production environment!")
        response = input("Are you sure you want to create an admin user? (yes/no): ")
        if response.lower() != "yes":
            print("❌ Admin user creation cancelled.")
            sys.exit(1)

    # Create admin user
    username, password = create_admin_user()

    if username and password:
        print(f"✅ Admin user created successfully!")
        print(f"   Username: {username}")
        print(f"   Password: {password}")
        print()
        print("🔒 SECURITY WARNING:")
        print("   - Change this password immediately after first login")
        print("   - Store this password securely")
        print("   - Delete this output from logs")
        print()
        print("📝 Next steps:")
        print("   1. Login with the credentials above")
        print("   2. Change the password immediately")
        print("   3. Configure OAuth2/OIDC authentication")
        print("   4. Delete this bootstrap script output")
    else:
        print("❌ Failed to create admin user")
        sys.exit(1)


if __name__ == "__main__":
    main()
