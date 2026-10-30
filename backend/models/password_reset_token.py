"""
PasswordResetToken ORM model — maps to the `password_reset_tokens` table.

See database/migrations/012_create_password_reset_tokens_table.sql for the
full design rationale (hashed storage, single-use via used_at, cascade delete).
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


def _utcnow() -> datetime:
    """Timezone-aware "now", matching the DateTime(timezone=True) columns
    below. A plain datetime.utcnow() default would hand back a naive
    datetime that Postgres stores fine on first insert but that Python
    would then choke on comparing against the aware values used
    everywhere else (is_valid below, and Ticket had exactly this bug —
    see backend/models/ticket.py's resolved_at/closed_at/sla_due_at)."""
    return datetime.now(timezone.utc)


class PasswordResetToken(Base):
    """A single-use, expiring token issued for the Forgot Password flow."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # SHA-256 hex digest (64 chars) of the raw token — see migration docstring
    # for why this isn't stored (or hashed) the same way as a password.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    user = relationship("User")

    @property
    def is_valid(self) -> bool:
        """True if the token hasn't been used and hasn't expired yet."""
        if self.used_at is not None:
            return False
        return datetime.now(timezone.utc) < self.expires_at

    def __repr__(self) -> str:
        return f"<PasswordResetToken id={self.id} user_id={self.user_id} used={self.used_at is not None}>"
