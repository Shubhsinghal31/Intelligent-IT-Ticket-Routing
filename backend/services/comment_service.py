"""
Comment business logic.

Handles creating and listing comments with RBAC applied.
"""

from loguru import logger
from sqlalchemy.orm import Session

from backend.core.exceptions import ForbiddenException, NotFoundException
from backend.models.comment import Comment
from backend.models.ticket import Ticket
from backend.models.user import User
from backend.repositories.comment_repository import CommentRepository
from backend.repositories.ticket_repository import TicketRepository
from backend.schemas.comment import CommentCreate


class CommentService:
    """Encapsulates comment workflows."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.comment_repo = CommentRepository(db)
        self.ticket_repo = TicketRepository(db)

    def _get_ticket_or_404(self, ticket_id: int) -> Ticket:
        ticket = self.ticket_repo.get_by_id(ticket_id)
        if not ticket:
            raise NotFoundException(f"Ticket {ticket_id} not found")
        return ticket

    def _assert_can_view(self, ticket: Ticket, user: User) -> None:
        """Employees can only view their own tickets."""
        if user.role.name == "employee" and ticket.created_by_id != user.id:
            raise ForbiddenException("You can only comment on your own tickets")

    # =====================================================
    # Create comment
    # =====================================================

    def create_comment(self, ticket_id: int, user: User, data: CommentCreate) -> Comment:
        """
        Add a comment to a ticket.

        Rules:
        - User must be able to view the ticket (employees: own tickets only)
        - Employees cannot post internal comments
        - author_id is always set from the authenticated user
        """
        ticket = self._get_ticket_or_404(ticket_id)
        self._assert_can_view(ticket, user)

        # Employees cannot post internal notes
        if data.is_internal and user.role.name == "employee":
            raise ForbiddenException("Employees cannot post internal comments")

        comment = Comment(
            ticket_id=ticket_id,
            author_id=user.id,
            body=data.body,
            is_internal=data.is_internal,
        )

        self.comment_repo.add(comment)
        self.comment_repo.commit()
        self.db.refresh(comment)

        logger.info(
            f"Comment created: id={comment.id} "
            f"ticket_id={ticket_id} "
            f"author_id={user.id} "
            f"internal={comment.is_internal}"
        )
        return comment

    # =====================================================
    # List comments
    # =====================================================

    def get_comments(
        self,
        ticket_id: int,
        user: User,
        page: int = 1,
        page_size: int = 50,
    ) -> list[Comment]:
        """
        Return comments for a ticket with RBAC applied.

        Employees only see non-internal comments and only on their own tickets.
        Engineers and admins see all comments including internal ones.
        """
        ticket = self._get_ticket_or_404(ticket_id)
        self._assert_can_view(ticket, user)

        include_internal = user.role.name in ("engineer", "admin")

        return self.comment_repo.get_by_ticket(
            ticket_id=ticket_id,
            include_internal=include_internal,
            page=page,
            page_size=page_size,
        )
