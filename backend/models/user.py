"""
User ORM model — maps to the `users` table.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base

if TYPE_CHECKING:
    from backend.models.department import Department
    from backend.models.role import Role


class User(Base):
    """Authenticated user account."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)

    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False
    )
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL")
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column()

    # ⭐ Pass class name as STRING — first positional arg to relationship()
    role: Mapped["Role"] = relationship("Role", back_populates="users", lazy="joined")
    department: Mapped["Department | None"] = relationship(
        "Department", back_populates="users", lazy="joined"
    )

    reported_tickets = relationship(
        "Ticket", foreign_keys="Ticket.created_by_id", back_populates="reporter"
    )
    assigned_tickets = relationship(
        "Ticket", foreign_keys="Ticket.assigned_to_id", back_populates="assignee"
    )

    def __repr__(self) -> str:
        role_name = self.role.name if self.role else None
        return f"<User id={self.id} email={self.email} role={role_name}>"
