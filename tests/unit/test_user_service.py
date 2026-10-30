"""
Unit tests for UserService business logic.

These mock the repository and DB session, so they run without a real
database connection — same convention as test_ticket_service.py.
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from backend.schemas.user import UserCreate
from backend.services.user_service import UserService


def make_service():
    """Return a UserService with a mocked DB session and repository."""
    db = MagicMock()
    service = UserService(db)
    service.user_repo = MagicMock()
    return service


def make_create_payload(**overrides) -> UserCreate:
    defaults = {
        "email": "new.engineer@example.com",
        "username": "new_engineer",
        "password": "SecurePass123!",
        "full_name": "New Engineer",
        "role": "engineer",
    }
    defaults.update(overrides)
    return UserCreate(**defaults)


# =====================================================
# Tests — get_users (listing + pagination math)
# =====================================================


class TestGetUsers:

    def test_returns_paginated_shape(self):
        service = make_service()
        service.user_repo.get_paginated.return_value = [MagicMock(), MagicMock()]
        service.user_repo.count.return_value = 2

        result = service.get_users(page=1, page_size=20)

        assert result["total"] == 2
        assert result["page"] == 1
        assert result["total_pages"] == 1
        assert len(result["items"]) == 2

    def test_total_pages_rounds_up(self):
        service = make_service()
        service.user_repo.get_paginated.return_value = []
        service.user_repo.count.return_value = 25  # 25 users, page_size=20 -> 2 pages

        result = service.get_users(page=1, page_size=20)

        assert result["total_pages"] == 2

    def test_empty_result_has_one_total_page(self):
        service = make_service()
        service.user_repo.get_paginated.return_value = []
        service.user_repo.count.return_value = 0

        result = service.get_users(page=1, page_size=20)

        assert result["total_pages"] == 1

    def test_forwards_filters_to_repository(self):
        service = make_service()
        service.user_repo.get_paginated.return_value = []
        service.user_repo.count.return_value = 0

        service.get_users(page=2, page_size=10, role="engineer", department_id=3, is_active=True)

        service.user_repo.get_paginated.assert_called_once_with(
            page=2, page_size=10, role_name="engineer", department_id=3, is_active=True
        )
        service.user_repo.count.assert_called_once_with(
            role_name="engineer", department_id=3, is_active=True
        )


# =====================================================
# Tests — create_user (admin-side provisioning)
# =====================================================


class TestCreateUser:

    def test_creates_user_with_resolved_role(self, engineer_role):
        service = make_service()
        service.user_repo.email_exists.return_value = False
        service.user_repo.username_exists.return_value = False
        service.user_repo.get_role_by_name.return_value = engineer_role

        with patch("backend.services.user_service.hash_password", return_value="hashed-value"):
            result = service.create_user(make_create_payload())

        assert result.role_id == engineer_role.id
        assert result.email == "new.engineer@example.com"
        assert result.username == "new_engineer"
        assert result.password_hash == "hashed-value"
        assert result.is_active is True
        service.user_repo.get_role_by_name.assert_called_once_with("engineer")
        service.user_repo.add.assert_called_once()
        service.user_repo.commit.assert_called_once()

    def test_department_id_none_skips_department_lookup(self, engineer_role):
        service = make_service()
        service.user_repo.email_exists.return_value = False
        service.user_repo.username_exists.return_value = False
        service.user_repo.get_role_by_name.return_value = engineer_role

        with patch("backend.services.user_service.hash_password", return_value="hashed-value"):
            result = service.create_user(make_create_payload(department_id=None))

        assert result.department_id is None
        service.db.get.assert_not_called()

    def test_valid_department_id_is_assigned(self, engineer_role):
        service = make_service()
        service.user_repo.email_exists.return_value = False
        service.user_repo.username_exists.return_value = False
        service.user_repo.get_role_by_name.return_value = engineer_role
        service.db.get.return_value = MagicMock(id=3)

        with patch("backend.services.user_service.hash_password", return_value="hashed-value"):
            result = service.create_user(make_create_payload(department_id=3))

        assert result.department_id == 3

    def test_duplicate_email_raises_conflict(self):
        service = make_service()
        service.user_repo.email_exists.return_value = True

        with pytest.raises(ConflictException, match="already registered"):
            service.create_user(make_create_payload())

        service.user_repo.username_exists.assert_not_called()

    def test_duplicate_username_raises_conflict(self):
        service = make_service()
        service.user_repo.email_exists.return_value = False
        service.user_repo.username_exists.return_value = True

        with pytest.raises(ConflictException, match="already taken"):
            service.create_user(make_create_payload())

    def test_unknown_role_raises_not_found(self):
        service = make_service()
        service.user_repo.email_exists.return_value = False
        service.user_repo.username_exists.return_value = False
        service.user_repo.get_role_by_name.return_value = None

        with pytest.raises(NotFoundException, match="does not exist"):
            service.create_user(make_create_payload(role="not_a_real_role"))

    def test_unknown_department_id_raises_not_found(self, engineer_role):
        service = make_service()
        service.user_repo.email_exists.return_value = False
        service.user_repo.username_exists.return_value = False
        service.user_repo.get_role_by_name.return_value = engineer_role
        service.db.get.return_value = None

        with pytest.raises(NotFoundException, match="Department 999 not found"):
            service.create_user(make_create_payload(department_id=999))

    def test_email_is_lowercased(self, engineer_role):
        # Note: username can't be tested the same way — UserBase's pattern
        # (^[a-z0-9_]+$) already rejects uppercase at the schema layer, so
        # only email (a plain EmailStr with no case constraint) exercises
        # the service's own .lower() call here.
        service = make_service()
        service.user_repo.email_exists.return_value = False
        service.user_repo.username_exists.return_value = False
        service.user_repo.get_role_by_name.return_value = engineer_role

        with patch("backend.services.user_service.hash_password", return_value="hashed-value"):
            result = service.create_user(make_create_payload(email="New.Engineer@Example.com"))

        assert result.email == "new.engineer@example.com"


# =====================================================
# Tests — deactivate_user
# =====================================================


class TestDeactivateUser:

    def test_admin_can_deactivate_another_user(self, admin_user):
        service = make_service()
        target = MagicMock(id=99, is_active=True)
        service.user_repo.get_by_id.return_value = target

        result = service.deactivate_user(99, admin_user)

        assert result.is_active is False
        service.user_repo.commit.assert_called_once()

    def test_admin_cannot_deactivate_self(self, admin_user):
        service = make_service()

        with pytest.raises(ForbiddenException, match="cannot deactivate your own account"):
            service.deactivate_user(admin_user.id, admin_user)

        service.user_repo.get_by_id.assert_not_called()

    def test_raises_404_for_missing_user(self, admin_user):
        service = make_service()
        service.user_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundException):
            service.deactivate_user(999, admin_user)


# =====================================================
# Tests — activate_user
# =====================================================


class TestActivateUser:

    def test_admin_can_activate_user(self, admin_user):
        service = make_service()
        target = MagicMock(id=99, is_active=False)
        service.user_repo.get_by_id.return_value = target

        result = service.activate_user(99, admin_user)

        assert result.is_active is True
        service.user_repo.commit.assert_called_once()

    def test_raises_404_for_missing_user(self, admin_user):
        service = make_service()
        service.user_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundException):
            service.activate_user(999, admin_user)
