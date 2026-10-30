"""
Centralized model exports.

Importing models here ensures Alembic and SQLAlchemy detect them
via Base.metadata BEFORE any relationship resolution occurs.
"""

from backend.models.attachment import Attachment
from backend.models.base import Base
from backend.models.comment import Comment
from backend.models.department import Department
from backend.models.password_reset_token import PasswordResetToken
from backend.models.role import Role
from backend.models.sla_policy import SlaPolicy
from backend.models.ticket import Ticket, TicketPriority, TicketStatus
from backend.models.ticket_history import TicketHistory
from backend.models.user import User

__all__ = [
    "Base",
    "Role",
    "Department",
    "User",
    "Ticket",
    "TicketStatus",
    "TicketPriority",
    "Comment",
    "Attachment",
    "SlaPolicy",
    "TicketHistory",
    "PasswordResetToken",
]
