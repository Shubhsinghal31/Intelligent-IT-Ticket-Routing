"""
Token-related Pydantic schemas.
"""

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    """Returned after successful login or refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token lifetime in seconds")


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    """Decoded JWT payload."""

    sub: str  # user id (as string per JWT RFC)
    type: str
    iat: int
    exp: int
    role: str | None = None
