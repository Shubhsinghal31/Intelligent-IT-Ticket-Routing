"""
TicketHistory ORM model.

Matches the ticket_history table created in Milestone 1 SQL
(database/migrations/009_create_ticket_history_table.sql). Writes added
as a post-Milestone-11 gap — see TicketService._record_history for the
instrumentation and backend/services/ticket_service.py for which fields
are tracked.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


class TicketHistory(Base):
    """Immutable audit log of every tracked field change on a ticket."""

    __tablename__ = "ticket_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    changed_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    field_changed: Mapped[str] = mapped_column(String(50), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    # DB uses changed_at, not created_at/updated_at
    changed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # No back_populates on Ticket/User — same reasoning as Comment.author
    # and Attachment.uploaded_by: history rows are only ever navigated
    # from ticket_id -> history, never the reverse via ORM.
    changed_by = relationship("User", foreign_keys=[changed_by_id])

    def __repr__(self) -> str:
        return (
            f"<TicketHistory id={self.id} ticket_id={self.ticket_id} "
            f"field={self.field_changed}>"
        )
