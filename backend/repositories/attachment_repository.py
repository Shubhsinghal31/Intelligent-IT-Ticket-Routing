"""
Attachment-specific repository operations.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.models.attachment import Attachment
from backend.repositories.base import BaseRepository


class AttachmentRepository(BaseRepository[Attachment]):
    """Repository for Attachment entity."""

    def __init__(self, db: Session) -> None:
        super().__init__(Attachment, db)

    def get_by_ticket(self, ticket_id: int) -> list[Attachment]:
        """
        Fetch all attachments for a ticket, oldest first.

        Unlike CommentRepository.get_by_ticket, this is not paginated —
        attachment counts per ticket are small in practice (a handful of
        screenshots/logs), so a single unpaginated list keeps the
        frontend simple. Revisit if that assumption stops holding.
        """
        stmt = (
            select(Attachment)
            .options(joinedload(Attachment.uploaded_by))  # avoid N+1 on uploader
            .where(Attachment.ticket_id == ticket_id)
            .order_by(Attachment.uploaded_at.asc())
        )
        return self.db.scalars(stmt).unique().all()
