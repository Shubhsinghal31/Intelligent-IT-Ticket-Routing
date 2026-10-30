"""
Department ORM model — maps to the `departments` table.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base

if TYPE_CHECKING:
    from backend.models.user import User


class Department(Base):
    """Department that handles tickets (IT, HR, Network, etc.)."""

    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    users: Mapped[list["User"]] = relationship("User", back_populates="department")
    tickets = relationship("Ticket", back_populates="department")

    def __repr__(self) -> str:
        return f"<Department id={self.id} name={self.name}>"
