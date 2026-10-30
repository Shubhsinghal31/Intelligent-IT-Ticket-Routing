"""
Shared ORM base and mixins.

Base is owned by database.py (connection layer).
We re-export it here alongside TimestampMixin for convenience.
"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

# Import Base from database — direct import, not through models/__init__.py
# This avoids circular imports because database.py does NOT import from models/
from backend.core.database import Base

__all__ = ["Base"]


class TimestampMixin:
    """
    Adds created_at and updated_at columns to any model.

    Usage:
        class Ticket(Base, TimestampMixin):
            __tablename__ = "tickets"
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
