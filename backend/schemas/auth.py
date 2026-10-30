"""
Auth request schemas.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator

from backend.utils.password_validator import (
    PasswordValidationError,
    validate_password_strength,
)


class LoginRequest(BaseModel):
    """Email + password login."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class ForgotPasswordRequest(BaseModel):
    """Request to begin a password reset."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Redeem a reset token for a new password."""

    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def check_strength(cls, v: str) -> str:
        try:
            validate_password_strength(v)
        except PasswordValidationError as e:
            raise ValueError(str(e)) from e
        return v
