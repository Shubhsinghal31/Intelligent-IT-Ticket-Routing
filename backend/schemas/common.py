"""
Pydantic schemas shared across endpoints.
"""

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class HealthCheckResponse(BaseModel):
    """Response for /health endpoint."""

    status: str = Field(..., examples=["ok"])
    app_name: str
    app_version: str
    environment: str
    database_connected: bool
    timestamp: datetime


class ErrorResponse(BaseModel):
    """
    Standardized error response — every error the API returns (4xx or 5xx)
    is shaped like this. See backend/main.py's exception handlers, which
    are what actually populate error_code and request_id; raising an
    AppException elsewhere in the codebase only needs to set `detail`.
    """

    detail: str
    error_code: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: str | None = Field(
        default=None,
        description="Correlates this error with server log lines — "
        "also returned as the X-Request-ID response header.",
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    model_config = ConfigDict(arbitrary_types_allowed=True)
