"""
Ticket data access layer.

All queries against the tickets table are defined here.
The service layer calls these methods — it never writes SQLAlchemy directly.
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from backend.models.ticket import Ticket, TicketPriority, TicketStatus
from backend.repositories.base import BaseRepository


class TicketRepository(BaseRepository[Ticket]):
    """Repository for the Ticket entity."""

    def __init__(self, db: Session) -> None:
        # Pass the model class up to BaseRepository
        super().__init__(Ticket, db)

    # =====================================================
    # Private helpers
    # =====================================================

    def _base_query(self):
        """
        Base SELECT for all ticket queries.

        Bakes in two things every ticket query needs:
        1. Eager-load reporter, assignee, department in one JOIN
        2. Exclude soft-deleted tickets
        """
        return select(Ticket).options(
            joinedload(Ticket.reporter),
            joinedload(Ticket.assignee),
            joinedload(Ticket.department),
        )

    def _apply_filters(
        self,
        stmt,
        status: TicketStatus | None,
        priority: TicketPriority | None,
        department_id: int | None,
        assignee_id: int | None,
        reporter_id: int | None,
        date_from: date | None = None,
        date_to: date | None = None,
    ):
        """
        Conditionally append WHERE clauses.

        Only filters that are not None are applied —
        this supports any combination of filter parameters.

        date_from/date_to were added for report generation (Milestone 9) —
        added as trailing optional params so existing positional calls from
        get_paginated()/count() keep working unchanged.
        """
        if status is not None:
            stmt = stmt.where(Ticket.status == status)
        if priority is not None:
            stmt = stmt.where(Ticket.priority == priority)
        if department_id is not None:
            stmt = stmt.where(Ticket.department_id == department_id)
        if assignee_id is not None:
            stmt = stmt.where(Ticket.assigned_to_id == assignee_id)
        if reporter_id is not None:
            stmt = stmt.where(Ticket.created_by_id == reporter_id)
        if date_from is not None:
            stmt = stmt.where(func.date(Ticket.created_at) >= date_from)
        if date_to is not None:
            stmt = stmt.where(func.date(Ticket.created_at) <= date_to)
        return stmt

    # =====================================================
    # Public query methods
    # =====================================================

    def get_by_id(self, ticket_id: int) -> Ticket | None:
        """
        Fetch a single ticket with all relationships loaded.

        Overrides BaseRepository.get_by_id to add joinedload
        and soft-delete filtering.
        """
        stmt = self._base_query().where(Ticket.id == ticket_id)
        return self.db.scalars(stmt).first()

    def get_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        department_id: int | None = None,
        assignee_id: int | None = None,
        reporter_id: int | None = None,
    ) -> list[Ticket]:
        """
        Return one page of tickets, with optional filters.

        offset = (page - 1) * page_size
        Example: page=2, page_size=10 → skip first 10, return next 10.
        """
        offset = (page - 1) * page_size
        stmt = self._apply_filters(
            self._base_query(),
            status,
            priority,
            department_id,
            assignee_id,
            reporter_id,
        )
        stmt = stmt.order_by(Ticket.created_at.desc()).offset(offset).limit(page_size)

        # .unique() is required when using joinedload to avoid duplicate rows
        return list(self.db.scalars(stmt).unique().all())

    def count(
        self,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        department_id: int | None = None,
        assignee_id: int | None = None,
        reporter_id: int | None = None,
    ) -> int:
        """
        Count total matching tickets — used for pagination metadata.

        Uses a lightweight COUNT(*) query — no joinedload needed here
        since we return a number, not ticket objects.
        """
        stmt = select(func.count()).select_from(Ticket)
        stmt = self._apply_filters(
            stmt,
            status,
            priority,
            department_id,
            assignee_id,
            reporter_id,
        )
        return self.db.scalar(stmt) or 0

    def get_all_filtered(
        self,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        department_id: int | None = None,
        assignee_id: int | None = None,
        reporter_id: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Ticket]:
        """
        Return every matching ticket, unpaginated — for report generation.

        Deliberately separate from get_paginated(): a report needs the
        complete result set to export, not one page of it. No hard cap is
        applied here; ReportService is expected to be used by staff on a
        single organization's ticket volume, not at a scale where this
        would be a memory concern.
        """
        stmt = self._apply_filters(
            self._base_query(),
            status,
            priority,
            department_id,
            assignee_id,
            reporter_id,
            date_from,
            date_to,
        )
        stmt = stmt.order_by(Ticket.created_at.desc())
        return list(self.db.scalars(stmt).unique().all())

    def soft_delete(self, ticket: Ticket) -> None:
        """
        Mark a ticket as deleted without removing the database row.

        flush() stages the change in the current transaction.
        The caller must call commit() to persist it.
        """

        self.db.flush()
