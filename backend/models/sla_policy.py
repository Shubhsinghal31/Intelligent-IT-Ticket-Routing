"""
SlaPolicy ORM model — stub for Milestone 5.

The sla_policies table was created in Milestone 1 SQL.
This stub registers the table with SQLAlchemy's metadata
so Alembic does not attempt to drop it.
"""

from sqlalchemy import Enum, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base
from backend.models.base import TimestampMixin


class SlaPolicy(Base, TimestampMixin):
    """SLA policy definitions (expanded in Milestone 5)."""

    __tablename__ = "sla_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    priority: Mapped[str] = mapped_column(
        Enum("low", "medium", "high", "critical", name="ticket_priority", create_type=False),
        nullable=False,
    )
    response_time_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_time_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
