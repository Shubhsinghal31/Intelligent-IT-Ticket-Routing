"""
Department-specific repository operations.
"""

from sqlalchemy import select

from backend.models.department import Department
from backend.repositories.base import BaseRepository


class DepartmentRepository(BaseRepository[Department]):
    """Repository for Department entity."""

    def __init__(self, db) -> None:
        super().__init__(Department, db)

    def list_active(self) -> list[Department]:
        """All active departments, alphabetical — used for picker UIs."""
        stmt = select(Department).where(Department.is_active.is_(True)).order_by(Department.name)
        return list(self.db.scalars(stmt).all())
