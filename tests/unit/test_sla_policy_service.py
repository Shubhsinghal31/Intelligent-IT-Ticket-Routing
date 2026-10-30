"""
Unit tests for SlaPolicyService business logic.

Mocks the repository/DB session — same convention as the other service tests.
"""

from unittest.mock import MagicMock

import pytest

from backend.core.exceptions import NotFoundException
from backend.schemas.sla_policy import SlaPolicyUpdate
from backend.services.sla_policy_service import SlaPolicyService


def make_service():
    db = MagicMock()
    service = SlaPolicyService(db)
    service.repo = MagicMock()
    return service


class TestListPolicies:

    def test_returns_repository_result(self):
        service = make_service()
        service.repo.get_all.return_value = [MagicMock(), MagicMock()]

        result = service.list_policies()

        assert len(result) == 2
        service.repo.get_all.assert_called_once()


class TestUpdatePolicy:

    def test_updates_provided_fields_only(self):
        service = make_service()
        policy = MagicMock(id=1, response_time_hours=2, resolution_time_hours=8, description="old")
        service.repo.get_by_id.return_value = policy

        result = service.update_policy(1, SlaPolicyUpdate(resolution_time_hours=12))

        assert result.resolution_time_hours == 12
        assert result.response_time_hours == 2  # untouched
        assert result.description == "old"  # untouched
        service.repo.commit.assert_called_once()

    def test_raises_404_for_missing_policy(self):
        service = make_service()
        service.repo.get_by_id.return_value = None

        with pytest.raises(NotFoundException):
            service.update_policy(999, SlaPolicyUpdate(resolution_time_hours=12))
