"""
Shared pytest fixtures for unit tests.

conftest.py is automatically loaded by pytest — no imports needed.
Fixtures defined here are available to all test files in this directory.
"""

from unittest.mock import MagicMock

import pytest

from backend.models.role import Role
from backend.models.ticket import Ticket, TicketPriority, TicketStatus
from backend.models.user import User

# =====================================================
# Role fixtures
# =====================================================


@pytest.fixture
def employee_role() -> Role:
    role = MagicMock(spec=Role)
    role.name = "employee"
    return role


@pytest.fixture
def engineer_role() -> Role:
    role = MagicMock(spec=Role)
    role.name = "engineer"
    return role


@pytest.fixture
def admin_role() -> Role:
    role = MagicMock(spec=Role)
    role.name = "admin"
    return role


# =====================================================
# User fixtures
# =====================================================


@pytest.fixture
def employee_user(employee_role) -> User:
    user = MagicMock(spec=User)
    user.id = 10
    user.username = "alice"
    user.is_active = True
    user.role = employee_role
    return user


@pytest.fixture
def engineer_user(engineer_role) -> User:
    user = MagicMock(spec=User)
    user.id = 20
    user.username = "bob"
    user.is_active = True
    user.role = engineer_role
    return user


@pytest.fixture
def admin_user(admin_role) -> User:
    user = MagicMock(spec=User)
    user.id = 1
    user.username = "admin"
    user.is_active = True
    user.role = admin_role
    return user


# =====================================================
# Ticket fixtures
# =====================================================


@pytest.fixture
def open_ticket(employee_user) -> Ticket:
    ticket = MagicMock(spec=Ticket)
    ticket.id = 1
    ticket.ticket_number = "TKT-2026-00001"
    ticket.title = "VPN not working"
    ticket.status = TicketStatus.OPEN
    ticket.priority = TicketPriority.MEDIUM
    ticket.created_by_id = employee_user.id  # owned by alice
    ticket.assigned_to_id = None
    ticket.resolved_at = None
    ticket.closed_at = None
    ticket.sla_due_at = None
    ticket.sla_breached = False
    return ticket


@pytest.fixture
def in_progress_ticket(open_ticket, engineer_user) -> Ticket:
    open_ticket.status = TicketStatus.IN_PROGRESS
    open_ticket.assigned_to_id = engineer_user.id
    return open_ticket


@pytest.fixture
def resolved_ticket(in_progress_ticket) -> Ticket:
    in_progress_ticket.status = TicketStatus.RESOLVED
    return in_progress_ticket


@pytest.fixture
def closed_ticket(resolved_ticket) -> Ticket:
    resolved_ticket.status = TicketStatus.CLOSED
    return resolved_ticket
