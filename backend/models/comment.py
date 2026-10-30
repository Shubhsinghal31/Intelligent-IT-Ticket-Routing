"""
Comment ORM model.

A comment belongs to a ticket and is authored by a user.
Maps to the 'comments' table from Milestone 1.
"""

from sqlalchemy import Boolean, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class Comment(Base, TimestampMixin):
    """
    Ticket comment entity.

    is_internal: True = visible to engineers/admins only (not the reporter).
    This is the 'private note' feature common in Jira and ServiceNow.
    """

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    ticket_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    body: Mapped[str] = mapped_column(Text, nullable=False)

    # Internal notes are only visible to engineers and admins
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    ticket = relationship("Ticket", back_populates="comments")
    author = relationship("User", foreign_keys=[author_id])

    def __repr__(self) -> str:
        return f"<Comment id={self.id} ticket_id={self.ticket_id}>"
