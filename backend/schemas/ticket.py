"""
Ticket request and response schemas.

Request schemas  — validate what the client sends.
Response schemas — shape what the API returns.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models.ticket import TicketPriority, TicketStatus

# =====================================================
# Supporting (nested) schemas
# =====================================================


class UserSummary(BaseModel):
    """
    Lightweight user info embedded in ticket responses.
    Avoids forcing the client to make a second API call.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str


class DepartmentSummary(BaseModel):
    """Lightweight department info embedded in ticket responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


# =====================================================
# Request schemas
# =====================================================


class TicketCreate(BaseModel):
    """
    Payload the client sends to create a ticket.

    reporter_id is NOT here — it comes from the authenticated
    user's token, injected by the dependency layer.
    """

    title: str = Field(
        ...,
        min_length=5,
        max_length=255,
        description="Brief summary of the issue",
    )
    description: str = Field(
        ...,
        min_length=20,
        description="Detailed explanation of the issue",
    )
    priority: TicketPriority = Field(
        default=TicketPriority.MEDIUM,
        description="Ticket urgency level",
    )
    department_id: int | None = Field(
        default=None,
        description="Target department (ML will predict if omitted)",
    )

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Title cannot be blank or whitespace only")
        return v.strip()

    @field_validator("description")
    @classmethod
    def description_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Description cannot be blank or whitespace only")
        return v.strip()


class TicketUpdate(BaseModel):
    """
    Partial update payload — all fields optional.

    PATCH semantics: only the fields provided are updated.
    Fields absent from the request body are left unchanged.
    """

    title: str | None = Field(default=None, min_length=5, max_length=255)
    description: str | None = Field(default=None, min_length=20)
    priority: TicketPriority | None = None
    department_id: int | None = None


class TicketAssign(BaseModel):
    """Payload to assign a ticket to an engineer."""

    assignee_id: int = Field(..., description="User ID of the engineer to assign")


# =====================================================
# Response schemas
# =====================================================


class TicketResponse(BaseModel):
    """
    Full ticket detail — returned for single-ticket endpoints.

    Nested objects (reporter, assignee, department) are used instead
    of raw IDs so the client gets everything in one request.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_number: str
    title: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    reporter: UserSummary
    assignee: UserSummary | None
    department: DepartmentSummary | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    sla_due_at: datetime | None
    closed_at: datetime | None
    sla_breached: bool

    # ML prediction fields
    predicted_priority_score: Decimal | None = None
    predicted_sla_breach_prob: Decimal | None = None
    predicted_resolution_hours: Decimal | None = None


class TicketSummary(BaseModel):
    """
    Lightweight ticket — used in paginated list responses.

    Omits description, SLA, and resolved_at to keep list payloads small.
    Full details are fetched via GET /tickets/{id}.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: TicketStatus
    priority: TicketPriority
    reporter: UserSummary
    assignee: UserSummary | None
    department: DepartmentSummary | None
    created_at: datetime
