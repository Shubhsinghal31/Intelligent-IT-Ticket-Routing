"""
Security primitives: password hashing + JWT encoding/decoding.

This module is the cryptographic foundation of authentication.
NEVER log raw passwords or tokens.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from loguru import logger
from passlib.context import CryptContext

from backend.core.config import settings
from backend.core.exceptions import UnauthorizedException

# =====================================================
# Password Hashing
# =====================================================
# Bcrypt with cost factor 12 (~100ms per hash on modern CPU)
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)


def hash_password(plain_password: str) -> str:
    """
    Hash a plain-text password using bcrypt.

    Args:
        plain_password: The password to hash.

    Returns:
        Bcrypt hash (60 chars).
    """
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against a stored hash.

    Args:
        plain_password: User-provided password.
        hashed_password: Stored bcrypt hash.

    Returns:
        True if match, False otherwise.
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.warning(f"Password verification error: {type(e).__name__}")
        return False


# =====================================================
# JWT Tokens
# =====================================================
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def _create_token(
    subject: str | int,
    token_type: str,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Internal helper to build a JWT.

    Claims:
        sub: subject (user ID as string)
        type: 'access' or 'refresh'
        iat: issued at
        exp: expiration
        + any extra claims (role, etc.)
    """
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_access_token(subject: str | int, extra_claims: dict[str, Any] | None = None) -> str:
    """Create a short-lived access token (~30 min)."""
    return _create_token(
        subject=subject,
        token_type=ACCESS_TOKEN_TYPE,
        expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        extra_claims=extra_claims,
    )


def create_refresh_token(subject: str | int) -> str:
    """Create a long-lived refresh token (~7 days)."""
    return _create_token(
        subject=subject,
        token_type=REFRESH_TOKEN_TYPE,
        expires_delta=timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str, expected_type: str | None = None) -> dict[str, Any]:
    """
    Decode and verify a JWT.

    Args:
        token: The JWT string.
        expected_type: If set, ensures token's 'type' claim matches.

    Returns:
        Decoded payload dict.

    Raises:
        UnauthorizedException: If token is invalid, expired, or wrong type.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as e:
        logger.warning(f"JWT decode failed: {e}")
        raise UnauthorizedException("Invalid or expired token") from e

    if expected_type and payload.get("type") != expected_type:
        raise UnauthorizedException(f"Expected {expected_type} token, got {payload.get('type')}")

    return payload
