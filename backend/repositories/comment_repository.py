"""
Comment-specific repository operations.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.models.comment import Comment
from backend.repositories.base import BaseRepository


class CommentRepository(BaseRepository[Comment]):
    """Repository for Comment entity."""

    def __init__(self, db: Session) -> None:
        super().__init__(Comment, db)

    def get_by_ticket(
        self,
        ticket_id: int,
        include_internal: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> list[Comment]:
        """
        Fetch paginated comments for a ticket.

        include_internal=False filters out is_internal=True rows.
        This enforces the rule that employees cannot see internal notes.
        """
        stmt = (
            select(Comment)
            .options(joinedload(Comment.author))  # avoid N+1 on author
            .where(Comment.ticket_id == ticket_id)
        )

        if not include_internal:
            stmt = stmt.where(Comment.is_internal == False)  # noqa: E712

        offset = (page - 1) * page_size
        stmt = stmt.order_by(Comment.created_at.asc()).offset(offset).limit(page_size)

        return self.db.scalars(stmt).unique().all()
