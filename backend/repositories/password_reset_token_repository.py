"""
Password reset token data access layer.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.password_reset_token import PasswordResetToken
from backend.repositories.base import BaseRepository


class PasswordResetTokenRepository(BaseRepository[PasswordResetToken]):
    """Repository for the PasswordResetToken entity."""

    def __init__(self, db: Session) -> None:
        super().__init__(PasswordResetToken, db)

    def get_by_token_hash(self, token_hash: str) -> PasswordResetToken | None:
        """Look up a token by its stored hash — the only way it's ever looked up."""
        stmt = select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        return self.db.scalars(stmt).first()
