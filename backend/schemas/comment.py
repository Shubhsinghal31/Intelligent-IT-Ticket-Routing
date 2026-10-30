"""
Comment request and response schemas.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.ticket import UserSummary


class CommentCreate(BaseModel):
    """Payload to add a comment to a ticket."""

    body: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Comment text",
    )
    is_internal: bool = Field(
        default=False,
        description="If true, only engineers and admins can see this comment",
    )


class CommentResponse(BaseModel):
    """Comment with embedded author info."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    body: str
    is_internal: bool
    author: UserSummary
    created_at: datetime
    updated_at: datetime
