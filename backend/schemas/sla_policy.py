"""
SLA policy request/response schemas.
"""

from pydantic import BaseModel, ConfigDict, Field


class SlaPolicyResponse(BaseModel):
    """SLA policy as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    priority: str
    response_time_hours: int
    resolution_time_hours: int
    description: str | None


class SlaPolicyUpdate(BaseModel):
    """
    Partial update payload for an SLA policy.

    PATCH semantics: only fields provided are changed. Priority is not
    editable — policies are keyed 1:1 to a TicketPriority value, and
    changing it would just be deleting one policy and orphaning another.
    """

    response_time_hours: int | None = Field(default=None, gt=0, le=720)
    resolution_time_hours: int | None = Field(default=None, gt=0, le=720)
    description: str | None = Field(default=None, max_length=500)
