"""
Unit tests for CommentService business logic.
"""

from unittest.mock import MagicMock

import pytest

from backend.core.exceptions import ForbiddenException, NotFoundException
from backend.services.comment_service import CommentService


def make_service():
    db = MagicMock()
    service = CommentService(db)
    service.comment_repo = MagicMock()
    service.ticket_repo = MagicMock()
    return service


class TestCreateComment:

    def test_employee_can_comment_on_own_ticket(self, employee_user, open_ticket):
        service = make_service()
        service.ticket_repo.get_by_id.return_value = open_ticket

        service.comment_repo.add.return_value = None
        service.db.refresh.return_value = None

        data = MagicMock()
        data.body = "Please fix this soon."
        data.is_internal = False

        # Should not raise
        service.create_comment(open_ticket.id, employee_user, data)

    def test_employee_cannot_comment_on_others_ticket(self, employee_user, open_ticket):
        open_ticket.created_by_id = 999  # not employee's ticket
        service = make_service()
        service.ticket_repo.get_by_id.return_value = open_ticket

        data = MagicMock()
        data.body = "Hey"
        data.is_internal = False

        with pytest.raises(ForbiddenException, match="your own tickets"):
            service.create_comment(open_ticket.id, employee_user, data)

    def test_employee_cannot_post_internal_comment(self, employee_user, open_ticket):
        service = make_service()
        service.ticket_repo.get_by_id.return_value = open_ticket

        data = MagicMock()
        data.body = "Internal note"
        data.is_internal = True  # employee trying to post internal

        with pytest.raises(ForbiddenException, match="internal comments"):
            service.create_comment(open_ticket.id, employee_user, data)

    def test_engineer_can_post_internal_comment(self, engineer_user, open_ticket):
        open_ticket.created_by_id = 999  # not engineer's ticket — engineers see all
        service = make_service()
        service.ticket_repo.get_by_id.return_value = open_ticket

        data = MagicMock()
        data.body = "Engineering note"
        data.is_internal = True

        # Should not raise
        service.create_comment(open_ticket.id, engineer_user, data)

    def test_raises_404_for_missing_ticket(self, employee_user):
        service = make_service()
        service.ticket_repo.get_by_id.return_value = None

        data = MagicMock()
        data.body = "Hello"
        data.is_internal = False

        with pytest.raises(NotFoundException):
            service.create_comment(999, employee_user, data)


class TestGetComments:

    def test_employee_sees_only_non_internal(self, employee_user, open_ticket):
        service = make_service()
        service.ticket_repo.get_by_id.return_value = open_ticket
        service.comment_repo.get_by_ticket.return_value = []

        service.get_comments(open_ticket.id, employee_user)

        service.comment_repo.get_by_ticket.assert_called_once_with(
            ticket_id=open_ticket.id,
            include_internal=False,
            page=1,
            page_size=50,
        )

    def test_engineer_sees_internal_comments(self, engineer_user, open_ticket):
        open_ticket.created_by_id = 999
        service = make_service()
        service.ticket_repo.get_by_id.return_value = open_ticket
        service.comment_repo.get_by_ticket.return_value = []

        service.get_comments(open_ticket.id, engineer_user)

        service.comment_repo.get_by_ticket.assert_called_once_with(
            ticket_id=open_ticket.id,
            include_internal=True,
            page=1,
            page_size=50,
        )
