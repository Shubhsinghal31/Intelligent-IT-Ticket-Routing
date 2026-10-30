"""
TicketHistory-specific repository operations.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.models.ticket_history import TicketHistory
from backend.repositories.base import BaseRepository


class TicketHistoryRepository(BaseRepository[TicketHistory]):
    """Repository for TicketHistory entity."""

    def __init__(self, db: Session) -> None:
        super().__init__(TicketHistory, db)

    def get_by_ticket(self, ticket_id: int) -> list[TicketHistory]:
        """
        Fetch the full audit trail for a ticket, oldest first -- a
        chronological timeline reads naturally top-to-bottom.

        Sorts by (changed_at, id), not changed_at alone. changed_at's
        DB default is CURRENT_TIMESTAMP, which in Postgres is
        *transaction* time, not statement/clock time -- it's frozen at
        the start of the enclosing transaction, not re-evaluated per
        row. TicketService.assign_ticket() can write two history rows
        (assigned_to_id, then status) inside the same commit, and those
        two rows get an IDENTICAL changed_at as a result. ORDER BY
        changed_at alone leaves ties in an arbitrary DB-decided order --
        id is autoincrement and always reflects true insertion order,
        so it's a reliable tiebreaker regardless of timestamp precision.
        """
        stmt = (
            select(TicketHistory)
            .options(joinedload(TicketHistory.changed_by))  # avoid N+1
            .where(TicketHistory.ticket_id == ticket_id)
            .order_by(TicketHistory.changed_at.asc(), TicketHistory.id.asc())
        )
        return self.db.scalars(stmt).unique().all()
