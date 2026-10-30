"""
Attachment ORM model.

Matches the attachments table created in Milestone 1 SQL
(database/migrations/008_create_attachments_table.sql). Full upload/
download workflow added as a post-Milestone-11 gap — see
backend/services/attachment_service.py for the storage design
(local disk, MIME allowlist, UUID-based safe filenames).
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


class Attachment(Base):
    """File attachments linked to tickets."""

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Relative to settings.ATTACHMENTS_STORAGE_PATH — never an absolute path.
    # See AttachmentService for why that matters (S3 migration later).
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # DB uses uploaded_at, not created_at/updated_at
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationships — no back_populates on Ticket/User side, mirroring
    # Comment.author (backend/models/comment.py): we only ever navigate
    # attachment -> ticket / attachment -> uploader, never the reverse
    # via ORM (repositories query attachments directly, filtered by
    # ticket_id), so a back-reference would be unused surface area.
    ticket = relationship("Ticket")
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_id])

    def __repr__(self) -> str:
        return f"<Attachment id={self.id} ticket_id={self.ticket_id} file_name={self.file_name}>"
