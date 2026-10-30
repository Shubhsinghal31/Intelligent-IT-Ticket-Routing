"""
Custom application exception hierarchy.

Why custom exceptions?
- Cleaner error handling than generic HTTPException everywhere
- Centralized HTTP status codes
- Easier to add logging/metrics per error type

Milestone 10 addition: error_code. Every subclass declares a stable,
machine-readable string (e.g. "NOT_FOUND") separate from `detail`, which
is a human-readable message that varies per raise site ("Ticket 5 not
found" vs "Department 3 not found"). The handler in backend/main.py
reads error_code to populate ErrorResponse.error_code — a frontend or
API consumer can branch on the code without parsing message text.
"""

from fastapi import HTTPException, status


class AppException(HTTPException):
    """Base class for all application exceptions."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "Internal server error"
    error_code: str = "INTERNAL_SERVER_ERROR"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(
            status_code=self.status_code,
            detail=detail or self.detail,
        )


class NotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Resource not found"
    error_code = "NOT_FOUND"


class UnauthorizedException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Authentication required"
    error_code = "UNAUTHORIZED"


class ForbiddenException(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "Insufficient permissions"
    error_code = "FORBIDDEN"


class ValidationException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    detail = "Validation failed"
    error_code = "VALIDATION_ERROR"


class ConflictException(AppException):
    status_code = status.HTTP_409_CONFLICT
    detail = "Resource conflict"
    error_code = "CONFLICT"


class DatabaseException(AppException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail = "Database error"
    error_code = "DATABASE_ERROR"
