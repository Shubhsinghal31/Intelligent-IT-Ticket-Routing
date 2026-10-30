"""
Ticket history (audit trail) response schema.

Read-only by design — there is no TicketHistoryCreate. Rows are written
exclusively by TicketService as a side effect of the lifecycle/update
methods it already exposes (see _record_history); there is no direct
"create a history entry" API, because an audit log a client could write
to arbitrarily wouldn't be trustworthy as an audit log.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.schemas.ticket import UserSummary


class TicketHistoryResponse(BaseModel):
    """One tracked field change on a ticket."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    field_changed: str
    old_value: str | None
    new_value: str | None
    changed_by: UserSummary
    changed_at: datetime
