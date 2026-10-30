"""
Unit tests for DepartmentService business logic.

This service is deliberately thin (see its module docstring), so there
isn't much branching logic to test — the point of these tests is to lock
in the pass-through contract: list_departments() calls the repository's
list_active() and returns exactly what it gives back, unchanged.
"""

from unittest.mock import MagicMock

from backend.services.department_service import DepartmentService


def make_service():
    """Return a DepartmentService with a mocked DB session and repository."""
    db = MagicMock()
    service = DepartmentService(db)
    service.department_repo = MagicMock()
    return service


class TestListDepartments:

    def test_returns_repository_result_unchanged(self):
        service = make_service()
        departments = [MagicMock(id=1, name="IT"), MagicMock(id=2, name="HR")]
        service.department_repo.list_active.return_value = departments

        result = service.list_departments()

        assert result == departments
        service.department_repo.list_active.assert_called_once_with()

    def test_empty_list_when_no_active_departments(self):
        service = make_service()
        service.department_repo.list_active.return_value = []

        result = service.list_departments()

        assert result == []
