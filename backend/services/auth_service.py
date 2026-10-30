"""
Authentication business logic.

Orchestrates: validation, password hashing, token issuance.
Endpoints are thin wrappers around this service.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.email import send_email
from backend.core.exceptions import (
    ConflictException,
    NotFoundException,
    UnauthorizedException,
)
from backend.core.security import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from backend.models.password_reset_token import PasswordResetToken
from backend.models.user import User
from backend.repositories.password_reset_token_repository import PasswordResetTokenRepository
from backend.repositories.user_repository import UserRepository
from backend.schemas.token import TokenResponse
from backend.schemas.user import UserRegister


class AuthService:
    """Encapsulates authentication workflows."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.reset_token_repo = PasswordResetTokenRepository(db)

    # =====================================================
    # Registration
    # =====================================================
    def register(self, data: UserRegister) -> User:
        """
        Register a new user with the default 'employee' role.

        Raises:
            ConflictException: If email or username already taken.
        """
        email = data.email.lower()
        username = data.username.lower()

        if self.user_repo.email_exists(email):
            raise ConflictException(f"Email '{email}' is already registered")
        if self.user_repo.username_exists(username):
            raise ConflictException(f"Username '{username}' is already taken")

        # Default new users to "employee" role
        role = self.user_repo.get_role_by_name("employee")
        if not role:
            raise NotFoundException("Default role 'employee' not configured")

        user = User(
            email=email,
            username=username,
            password_hash=hash_password(data.password),
            full_name=data.full_name,
            role_id=role.id,
            department_id=None,
            is_active=True,
        )
        self.user_repo.add(user)
        self.user_repo.commit()
        self.db.refresh(user)

        logger.info(f"New user registered: id={user.id} email={user.email}")
        return user

    # =====================================================
    # Login
    # =====================================================
    def authenticate(self, email: str, password: str) -> User:
        """
        Verify credentials and return the user.

        Raises:
            UnauthorizedException: On invalid credentials or inactive user.
        """
        user = self.user_repo.get_by_email(email.lower())

        # Constant-time response: always run bcrypt even if user not found
        # (prevents timing attacks that reveal which emails exist)
        if not user:
            # Dummy verify to consume similar CPU time
            verify_password(password, "$2b$12$" + "x" * 53)
            logger.warning(f"Login failed: email not found: {email}")
            raise UnauthorizedException("Invalid email or password")

        if not verify_password(password, user.password_hash):
            logger.warning(f"Login failed: bad password for user_id={user.id}")
            raise UnauthorizedException("Invalid email or password")

        if not user.is_active:
            logger.warning(f"Login blocked: inactive user_id={user.id}")
            raise UnauthorizedException("Account is disabled")

        self.user_repo.update_last_login(user)
        self.user_repo.commit()
        logger.info(f"Login successful: user_id={user.id}")
        return user

    # =====================================================
    # Token issuance
    # =====================================================
    def issue_tokens(self, user: User) -> TokenResponse:
        """Create access + refresh tokens for a user."""
        extra = {"role": user.role.name, "username": user.username}
        access = create_access_token(user.id, extra_claims=extra)
        refresh = create_refresh_token(user.id)

        return TokenResponse(
            access_token=access,
            refresh_token=refresh,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    # =====================================================
    # Refresh
    # =====================================================
    def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        """
        Issue a new access token from a valid refresh token.

        Raises:
            UnauthorizedException: If refresh token invalid/expired.
        """
        payload = decode_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
        user_id = int(payload["sub"])

        user = self.user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise UnauthorizedException("User no longer valid")

        return self.issue_tokens(user)

    # =====================================================
    # Change password
    # =====================================================
    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        """
        Verify the current password and update to the new one.

        Raises:
            UnauthorizedException: If current_password does not match.
        """
        if not verify_password(current_password, user.password_hash):
            raise UnauthorizedException("Current password is incorrect")

        user.password_hash = hash_password(new_password)
        self.user_repo.commit()
        logger.info(f"Password changed for user_id={user.id}")

    # =====================================================
    # Get current user from access token
    # =====================================================
    def get_user_from_token(self, token: str) -> User:
        """Decode access token and load the user."""
        payload = decode_token(token, expected_type=ACCESS_TOKEN_TYPE)
        user_id = int(payload["sub"])

        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise UnauthorizedException("User not found")
        if not user.is_active:
            raise UnauthorizedException("Account is disabled")
        return user

    # =====================================================
    # Forgot password — step 1: request a reset
    # =====================================================
    def request_password_reset(self, email: str) -> None:
        """
        Issue a password reset token and email it, if the account exists.

        Deliberately returns None either way — never raises for "email not
        found" and the endpoint always responds with the same generic
        message. This mirrors authenticate()'s user-enumeration defense
        above: an attacker probing which emails are registered shouldn't
        learn anything from a different response shape or timing here.

        The raw token is generated with `secrets.token_urlsafe`, a
        cryptographically secure RNG (not `random` — that's predictable
        enough to matter for anything security-sensitive). Only its
        SHA-256 hash is persisted; see PasswordResetToken's docstring for
        why SHA-256 (fast hash) is the right choice here and bcrypt
        (deliberately slow) would be the wrong one.
        """
        user = self.user_repo.get_by_email(email.lower())
        if not user or not user.is_active:
            logger.info(f"Password reset requested for unknown/inactive email: {email}")
            return

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
        )

        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.reset_token_repo.add(reset_token)
        self.reset_token_repo.commit()

        reset_link = f"{settings.FRONTEND_URL}?reset_token={raw_token}"
        send_email(
            to=user.email,
            subject="Reset your Helpdesk AI password",
            body=(
                f"Hi {user.full_name},\n\n"
                f"Someone requested a password reset for this account. "
                f"If this was you, use the link below within "
                f"{settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes:\n\n"
                f"{reset_link}\n\n"
                f"If you didn't request this, you can safely ignore this email — "
                f"your password will not be changed."
            ),
        )
        logger.info(f"Password reset token issued for user_id={user.id}")

    # =====================================================
    # Forgot password — step 2: redeem the token
    # =====================================================
    def reset_password(self, raw_token: str, new_password: str) -> None:
        """
        Validate a reset token and set the account's new password.

        Raises:
            UnauthorizedException: If the token is unknown, expired, or
                already used. Same exception type as bad-login-credentials
                — a wrong/expired/reused token is an authorization failure,
                not a "not found" (which would hint whether SOME token
                existed at that value).
        """
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        reset_token = self.reset_token_repo.get_by_token_hash(token_hash)

        if not reset_token or not reset_token.is_valid:
            logger.warning("Password reset attempted with invalid/expired/used token")
            raise UnauthorizedException("Invalid or expired reset token")

        user = self.user_repo.get_by_id(reset_token.user_id)
        if not user or not user.is_active:
            raise UnauthorizedException("Invalid or expired reset token")

        user.password_hash = hash_password(new_password)
        reset_token.used_at = datetime.now(timezone.utc)

        self.reset_token_repo.commit()
        logger.info(f"Password reset completed for user_id={user.id}")
