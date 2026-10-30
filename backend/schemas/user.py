"""
User-related Pydantic schemas (DTOs for API I/O).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from backend.utils.password_validator import (
    PasswordValidationError,
    validate_password_strength,
)


# =====================================================
# Base shapes
# =====================================================
class UserBase(BaseModel):
    """Common fields shared across schemas."""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-z0-9_]+$")
    full_name: str = Field(..., min_length=2, max_length=100)


# =====================================================
# Request: register
# =====================================================
class UserRegister(UserBase):
    """Schema for user self-registration."""

    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def check_password_strength(cls, v: str) -> str:
        try:
            validate_password_strength(v)
        except PasswordValidationError as e:
            raise ValueError(str(e)) from e
        return v


# =====================================================
# Request: admin creates user
# =====================================================
class UserCreate(UserRegister):
    """
    Admin-side user creation — can set role + department.

    Takes `role` as a name (e.g. "engineer"), not `role_id`, mirroring
    how the rest of the API deals with roles/priorities/statuses as
    strings rather than raw database IDs — a client of this API should
    never need to know that "engineer" happens to be role_id=2 in this
    particular database. UserService.create_user() resolves the name to
    a Role row server-side (raising NotFoundException if it doesn't
    match a seeded role), the same way AuthService.register() already
    resolves "employee" for self-registration.
    """

    role: str = Field(..., description="Role name, e.g. 'employee', 'engineer', or 'admin'")
    department_id: int | None = Field(default=None, gt=0)


# =====================================================
# Response: public user info
# =====================================================
class UserResponse(BaseModel):
    """User info returned to clients — NEVER includes password_hash."""

    id: int
    email: str  # str not EmailStr — response schemas don't re-validate stored data
    username: str
    full_name: str
    role: str  # role.name (e.g., "admin")
    department: str | None  # department.name
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_user(cls, user) -> "UserResponse":
        """Helper to flatten role.name and department.name."""
        return cls(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            role=user.role.name,
            department=user.department.name if user.department else None,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        )


# =====================================================
# Request: change password
# =====================================================
class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def check_strength(cls, v: str) -> str:
        try:
            validate_password_strength(v)
        except PasswordValidationError as e:
            raise ValueError(str(e)) from e
        return v
