"""
Ticket business logic.

Enforces business rules, RBAC, and coordinates between
the repository and the rest of the system.
The route layer calls this service — never the repository directly.
"""

import math
from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy.orm import Session

from backend.core.exceptions import ForbiddenException, NotFoundException
from backend.models.department import Department
from backend.models.sla_policy import SlaPolicy
from backend.models.ticket import Ticket, TicketPriority, TicketStatus
from backend.models.ticket_history import TicketHistory
from backend.models.user import User
from backend.repositories.ticket_history_repository import TicketHistoryRepository
from backend.repositories.ticket_repository import TicketRepository
from backend.schemas.ticket import TicketCreate, TicketUpdate
from ml.service import ml_service


class TicketService:
    """Encapsulates all ticket workflows."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.ticket_repo = TicketRepository(db)
        self.history_repo = TicketHistoryRepository(db)

    # =====================================================
    # Internal helpers
    # =====================================================

    def _get_ticket_or_404(self, ticket_id: int) -> Ticket:
        """
        Fetch a ticket by ID or raise NotFoundException.

        Centralises the "does this ticket exist?" check so
        every public method doesn't repeat the same pattern.
        """
        ticket = self.ticket_repo.get_by_id(ticket_id)
        if not ticket:
            raise NotFoundException(f"Ticket {ticket_id} not found")
        return ticket

    def _assert_can_view(self, ticket: Ticket, user: User) -> None:
        """
        Enforce read access rules.

        Employees can only view tickets they reported.
        Engineers and admins can view any ticket.
        """
        if user.role.name == "employee" and ticket.created_by_id != user.id:
            raise ForbiddenException("You can only view your own tickets")

    def _assert_can_modify(self, ticket: Ticket, user: User) -> None:
        """
        Enforce write access rules.

        Employees can only modify tickets they reported.
        Engineers and admins can modify any ticket.
        """
        if user.role.name == "employee" and ticket.created_by_id != user.id:
            raise ForbiddenException("You can only modify your own tickets")

    def _validate_department(self, department_id: int) -> Department:
        """
        Confirm the department exists and is active.

        Raises NotFoundException if department does not exist.
        Raises ForbiddenException if department is inactive.
        """
        department = self.db.get(Department, department_id)
        if not department:
            raise NotFoundException(f"Department {department_id} not found")
        if not department.is_active:
            raise ForbiddenException(f"Department '{department.name}' is not active")
        return department

    def _record_history(
        self,
        ticket: Ticket,
        user: User,
        field: str,
        old_value: str | None,
        new_value: str | None,
    ) -> None:
        """
        Append one audit-trail row, but only if the value actually changed.

        Rides along in the same DB transaction as the field mutation it
        documents — add() only flush()es, so this relies on whichever
        commit() the calling method already performs; there's no separate
        commit here. The no-op-on-no-change guard matters for methods
        like assign_ticket(), which can be called with an assignee_id
        equal to the current one — that's a legal no-op call, not an
        actual change, so it shouldn't leave a misleading entry in the
        trail.
        """
        if old_value == new_value:
            return
        self.history_repo.add(
            TicketHistory(
                ticket_id=ticket.id,
                changed_by_id=user.id,
                field_changed=field,
                old_value=old_value,
                new_value=new_value,
            )
        )

    # =====================================================
    # Create
    # =====================================================

    def create_ticket(self, reporter: User, data: TicketCreate) -> Ticket:
        """
        Create a new ticket.

        The reporter is always the authenticated user —
        clients cannot create tickets on behalf of others.

        Steps:
        1. Validate department if provided
        2. Build the Ticket ORM object
        3. Persist and commit
        4. Return the saved ticket
        """
        if data.department_id is not None:
            self._validate_department(data.department_id)

        ticket = Ticket(
            title=data.title,
            description=data.description,
            priority=data.priority,
            department_id=data.department_id,
            created_by_id=reporter.id,
            status=TicketStatus.OPEN,
            ticket_number="PENDING",  # temporary — real number set after flush OPEN
        )

        self.ticket_repo.add(ticket)  # flush() inside add() gives us ticket.id
        ticket.ticket_number = f"TKT-{datetime.now().year}-{ticket.id:05d}"

        # -----------------------------------------------
        # ML Predictions — run after ticket_number is set
        # -----------------------------------------------
        try:
            prediction = ml_service.predict(data.title, data.description)

            ticket.predicted_priority_score = prediction.priority_score
            ticket.predicted_sla_breach_prob = prediction.sla_breach_prob
            ticket.predicted_resolution_hours = prediction.resolution_hours

            # Auto-assign department if reporter didn't specify one
            if ticket.department_id is None and prediction.department_name:
                dept = (
                    self.db.query(Department)
                    .filter(Department.name == prediction.department_name)
                    .first()
                )
                if dept and dept.is_active:
                    ticket.department_id = dept.id
                    logger.info(
                        f"ML auto-assigned department: '{dept.name}' " f"for ticket_id={ticket.id}"
                    )

        except Exception as e:
            # Never let ML failure block ticket creation
            logger.error(f"ML prediction failed for ticket_id={ticket.id}: {e}")

        # -----------------------------------------------
        # SLA due date — based on the ticket's actual priority
        # (the reporter's/default choice), not the ML-predicted one.
        # sla_due_at is what resolve_ticket() checks to set sla_breached.
        # -----------------------------------------------
        policy = (
            self.db.query(SlaPolicy).filter(SlaPolicy.priority == ticket.priority.value).first()
        )
        if policy:
            ticket.sla_due_at = ticket.created_at + timedelta(hours=policy.resolution_time_hours)
        else:
            logger.warning(f"No SLA policy found for priority={ticket.priority.value}")

        self.ticket_repo.commit()
        self.db.refresh(ticket)

        logger.info(
            f"Ticket created: id={ticket.id} "
            f"reporter_id={reporter.id} "
            f"priority={ticket.priority}"
        )
        return ticket

    # =====================================================
    # Read — single ticket
    # =====================================================

    def get_ticket(self, ticket_id: int, requesting_user: User) -> Ticket:
        """
        Return a single ticket if the user has access.

        Raises NotFoundException if ticket does not exist.
        Raises ForbiddenException if user is not allowed to view it.
        """
        ticket = self._get_ticket_or_404(ticket_id)
        self._assert_can_view(ticket, requesting_user)
        return ticket

    # =====================================================
    # Read — paginated list
    # =====================================================

    def get_tickets(
        self,
        requesting_user: User,
        page: int = 1,
        page_size: int = 20,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        department_id: int | None = None,
        assignee_id: int | None = None,
    ) -> dict:
        """
        Return a paginated list of tickets with RBAC applied.

        Employees see only their own tickets.
        Engineers and admins see all tickets.

        Returns a dict compatible with PaginatedResponse[TicketSummary].
        """
        # RBAC: employees are restricted to their own tickets
        reporter_id = None
        if requesting_user.role.name == "employee":
            reporter_id = requesting_user.id

        tickets = self.ticket_repo.get_paginated(
            page=page,
            page_size=page_size,
            status=status,
            priority=priority,
            department_id=department_id,
            assignee_id=assignee_id,
            reporter_id=reporter_id,
        )

        total = self.ticket_repo.count(
            status=status,
            priority=priority,
            department_id=department_id,
            assignee_id=assignee_id,
            reporter_id=reporter_id,
        )

        return {
            "items": tickets,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total > 0 else 1,
        }

    # =====================================================
    # Update — partial field changes
    # =====================================================

    def update_ticket(self, ticket_id: int, user: User, data: TicketUpdate) -> Ticket:
        """
        Apply a partial update to a ticket's editable fields.

        Only fields explicitly provided in the request are changed.
        Status is NOT updatable here — use lifecycle methods instead.

        RBAC: reporters can update their own tickets,
              engineers and admins can update any ticket.
        """
        ticket = self._get_ticket_or_404(ticket_id)
        self._assert_can_modify(ticket, user)

        if data.title is not None:
            self._record_history(ticket, user, "title", ticket.title, data.title)
            ticket.title = data.title
        if data.description is not None:
            self._record_history(ticket, user, "description", ticket.description, data.description)
            ticket.description = data.description
        if data.priority is not None:
            self._record_history(
                ticket, user, "priority", ticket.priority.value, data.priority.value
            )
            ticket.priority = data.priority
        if data.department_id is not None:
            self._validate_department(data.department_id)
            self._record_history(
                ticket,
                user,
                "department_id",
                str(ticket.department_id) if ticket.department_id is not None else None,
                str(data.department_id),
            )
            ticket.department_id = data.department_id

        self.ticket_repo.commit()
        self.db.refresh(ticket)

        logger.info(f"Ticket updated: id={ticket.id} by user_id={user.id}")
        return ticket

    # =====================================================
    # Assign — set or change the engineer
    # =====================================================

    def assign_ticket(self, ticket_id: int, user: User, assignee_id: int) -> Ticket:
        """
        Assign a ticket to an engineer.

        Also transitions status from OPEN → IN_PROGRESS automatically.
        RBAC: engineers and admins only.

        Raises:
            ForbiddenException: If user is not engineer or admin.
            NotFoundException: If assignee user does not exist.
        """
        if user.role.name not in ("engineer", "admin"):
            raise ForbiddenException("Only engineers and admins can assign tickets")

        ticket = self._get_ticket_or_404(ticket_id)

        # Verify the assignee exists and is active
        from backend.models.user import User as UserModel

        assignee = self.db.get(UserModel, assignee_id)
        if not assignee or not assignee.is_active:
            raise NotFoundException(f"Engineer with id={assignee_id} not found or inactive")

        self._record_history(
            ticket,
            user,
            "assigned_to_id",
            str(ticket.assigned_to_id) if ticket.assigned_to_id is not None else None,
            str(assignee_id),
        )
        ticket.assigned_to_id = assignee_id

        # Auto-transition: OPEN ticket becomes IN_PROGRESS when assigned
        if ticket.status == TicketStatus.OPEN:
            self._record_history(
                ticket, user, "status", ticket.status.value, TicketStatus.IN_PROGRESS.value
            )
            ticket.status = TicketStatus.IN_PROGRESS

        self.ticket_repo.commit()
        self.db.refresh(ticket)

        logger.info(
            f"Ticket assigned: id={ticket.id} " f"assignee_id={assignee_id} by user_id={user.id}"
        )
        return ticket

    # =====================================================
    # Close — finalise a resolved ticket
    # =====================================================

    def close_ticket(self, ticket_id: int, user: User) -> Ticket:
        """
        Close a ticket, setting closed_at to now.

        Valid transitions: RESOLVED → CLOSED only.
        RBAC: engineers and admins only.

        Raises:
            ForbiddenException: If ticket is not in RESOLVED status.
        """
        if user.role.name not in ("engineer", "admin"):
            raise ForbiddenException("Only engineers and admins can close tickets")

        ticket = self._get_ticket_or_404(ticket_id)

        if ticket.status != TicketStatus.RESOLVED:
            raise ForbiddenException(
                f"Cannot close a ticket in '{ticket.status.value}' status. "
                f"Ticket must be RESOLVED first."
            )

        self._record_history(ticket, user, "status", ticket.status.value, TicketStatus.CLOSED.value)
        ticket.status = TicketStatus.CLOSED
        ticket.closed_at = datetime.now(timezone.utc)

        self.ticket_repo.commit()
        self.db.refresh(ticket)

        logger.info(f"Ticket closed: id={ticket.id} by user_id={user.id}")
        return ticket

    # =====================================================
    # Reopen — bring a closed or resolved ticket back
    # =====================================================

    def reopen_ticket(self, ticket_id: int, user: User) -> Ticket:
        """
        Reopen a CLOSED or RESOLVED ticket.

        Clears closed_at and resolved_at timestamps.
        RBAC: reporters can reopen their own tickets; engineers and admins can reopen any.

        Raises:
            ForbiddenException: If ticket is not in a reopenable state.
        """
        ticket = self._get_ticket_or_404(ticket_id)
        self._assert_can_modify(ticket, user)

        reopenable_statuses = {TicketStatus.CLOSED, TicketStatus.RESOLVED}
        if ticket.status not in reopenable_statuses:
            raise ForbiddenException(
                f"Cannot reopen a ticket in '{ticket.status.value}' status. "
                f"Only CLOSED or RESOLVED tickets can be reopened."
            )

        self._record_history(
            ticket, user, "status", ticket.status.value, TicketStatus.REOPENED.value
        )
        ticket.status = TicketStatus.REOPENED
        ticket.closed_at = None
        ticket.resolved_at = None

        self.ticket_repo.commit()
        self.db.refresh(ticket)

        logger.info(f"Ticket reopened: id={ticket.id} by user_id={user.id}")
        return ticket

    # =====================================================
    # Resolve — engineer marks the ticket as fixed
    # =====================================================
    def resolve_ticket(self, ticket_id: int, user: User) -> Ticket:
        """..."""
        if user.role.name not in ("engineer", "admin"):
            raise ForbiddenException("Only engineers and admins can resolve tickets")

        ticket = self._get_ticket_or_404(ticket_id)

        resolvable_statuses = {TicketStatus.IN_PROGRESS, TicketStatus.REOPENED}
        if ticket.status not in resolvable_statuses:
            raise ForbiddenException(
                f"Cannot resolve a ticket in '{ticket.status.value}' status. "
                f"Ticket must be IN_PROGRESS or REOPENED."
            )

        self._record_history(
            ticket, user, "status", ticket.status.value, TicketStatus.RESOLVED.value
        )
        ticket.status = TicketStatus.RESOLVED
        ticket.resolved_at = datetime.now(timezone.utc)

        # Compare against the due date set at creation time (see create_ticket).
        # sla_due_at can be None if no SlaPolicy existed for the priority —
        # in that case there is nothing to breach against.
        if ticket.sla_due_at and ticket.resolved_at > ticket.sla_due_at:
            ticket.sla_breached = True
            logger.warning(f"SLA breached: ticket_id={ticket.id} resolved after due date")

        self.ticket_repo.commit()
        self.db.refresh(ticket)

        logger.info(f"Ticket resolved: id={ticket.id} by user_id={user.id}")
        return ticket

    # =====================================================
    # History — read the audit trail
    # =====================================================

    def get_history(self, ticket_id: int, user: User) -> list[TicketHistory]:
        """
        Return the full audit trail for a ticket, oldest first.

        Same view RBAC as get_ticket(): if you can't see the ticket, you
        can't see its history either — an audit trail is strictly more
        sensitive than the ticket's current state, never less.
        """
        ticket = self._get_ticket_or_404(ticket_id)
        self._assert_can_view(ticket, user)
        return self.history_repo.get_by_ticket(ticket_id)
