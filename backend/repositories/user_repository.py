"""
User-specific repository operations.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from backend.models.role import Role
from backend.models.user import User
from backend.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User entity."""

    def __init__(self, db: Session) -> None:
        super().__init__(User, db)

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower())
        return self.db.scalars(stmt).first()

    def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username.lower())
        return self.db.scalars(stmt).first()

    def email_exists(self, email: str) -> bool:
        return self.get_by_email(email) is not None

    def username_exists(self, username: str) -> bool:
        return self.get_by_username(username) is not None

    def get_role_by_name(self, name: str) -> Role | None:
        stmt = select(Role).where(Role.name == name.lower())
        return self.db.scalars(stmt).first()

    def update_last_login(self, user: User) -> None:
        user.last_login_at = datetime.now(timezone.utc)
        self.db.flush()

    # =====================================================
    # Listing — mirrors TicketRepository's filter/paginate pattern
    # =====================================================

    def _base_query(self):
        """Eager-load role + department in one JOIN for every listing query."""
        return select(User).options(
            joinedload(User.role),
            joinedload(User.department),
        )

    def _apply_filters(
        self,
        stmt,
        role_name: str | None,
        department_id: int | None,
        is_active: bool | None,
    ):
        """Conditionally append WHERE clauses — only non-None filters apply."""
        if role_name is not None:
            stmt = stmt.where(Role.name == role_name).join(Role, User.role_id == Role.id)
        if department_id is not None:
            stmt = stmt.where(User.department_id == department_id)
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
        return stmt

    def get_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        role_name: str | None = None,
        department_id: int | None = None,
        is_active: bool | None = None,
    ) -> list[User]:
        """Return one page of users, with optional role/department/status filters."""
        offset = (page - 1) * page_size
        stmt = self._apply_filters(self._base_query(), role_name, department_id, is_active)
        stmt = stmt.order_by(User.full_name).offset(offset).limit(page_size)
        return list(self.db.scalars(stmt).unique().all())

    def count(
        self,
        role_name: str | None = None,
        department_id: int | None = None,
        is_active: bool | None = None,
    ) -> int:
        """Count total matching users — used for pagination metadata."""
        stmt = select(func.count()).select_from(User)
        stmt = self._apply_filters(stmt, role_name, department_id, is_active)
        return self.db.scalar(stmt) or 0
