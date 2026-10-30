"""
Department business logic.

Deliberately thin — departments are seed-managed reference data today
(see database/seeds/002_seed_departments.sql), not user-editable through
the API. This service exists as a real layer anyway (rather than the
endpoint querying the repository directly) so that if department
CRUD is ever added, RBAC/validation has an obvious home to live in
without restructuring the call chain.
"""

from sqlalchemy.orm import Session

from backend.models.department import Department
from backend.repositories.department_repository import DepartmentRepository


class DepartmentService:
    """Encapsulates department workflows."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.department_repo = DepartmentRepository(db)

    def list_departments(self) -> list[Department]:
        """All active departments, alphabetical."""
        return self.department_repo.list_active()
