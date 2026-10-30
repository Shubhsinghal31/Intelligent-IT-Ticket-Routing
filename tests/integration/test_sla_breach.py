"""
SLA due-date and breach-detection integration tests.

Exercises the real chain: TicketService.create_ticket() looks up a
SlaPolicy matching the ticket's priority and sets sla_due_at; later,
TicketService.resolve_ticket() compares resolved_at against that due
date to decide sla_breached; DashboardService.get_sla_stats() then
aggregates breaches per department for the two cases it defines:
  1. Already resolved late (Ticket.sla_breached == True)
  2. Still open/in-progress and already past its due date
     ("currently overdue" — case 2 in get_sla_stats' docstring)

Each test seeds its own SlaPolicy row directly via db_session rather
than relying on any pre-seeded policy — conftest.py only seeds roles
and departments, not SLA policies, so tests control exactly which
priority/resolution_time_hours they're asserting against. Because
db_session is the same transactional session the TestClient's requests
run against (see the `client` fixture's dependency override), a row
added here via db_session.add()/flush() is visible to the very next
HTTP call without needing a real commit — and everything is rolled
back at teardown regardless.
"""

from datetime import datetime, timedelta, timezone

from backend.models.department import Department
from backend.models.sla_policy import SlaPolicy
from backend.models.ticket import Ticket
from tests.integration.conftest import auth_headers, create_active_user, login, register


def _seed_sla_policy(db_session, priority: str, resolution_time_hours: int) -> SlaPolicy:
    policy = SlaPolicy(
        priority=priority,
        response_time_hours=1,
        resolution_time_hours=resolution_time_hours,
        description=f"Test policy for {priority}",
    )
    db_session.add(policy)
    db_session.flush()
    return policy


def _get_department_id(db_session, name: str = "IT Support") -> int:
    return db_session.query(Department).filter(Department.name == name).one().id


def _create_ticket(client, token: str, department_id: int, priority: str, title: str) -> dict:
    response = client.post(
        "/api/v1/tickets",
        headers=auth_headers(token),
        json={
            "title": title,
            "description": "Detailed description of the issue, at least 20 characters.",
            "priority": priority,
            "department_id": department_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


# =====================================================
# sla_due_at is set at creation time from the matching policy
# =====================================================


class TestSlaDueDateAssignment:
    def test_ticket_gets_sla_due_at_from_matching_policy(self, client, db_session):
        _seed_sla_policy(db_session, priority="critical", resolution_time_hours=4)
        department_id = _get_department_id(db_session)

        register(client, "sla.creator@example.com", "sla_creator", "SLA Creator")
        token = login(client, "sla.creator@example.com")

        ticket = _create_ticket(client, token, department_id, "critical", "Production outage")

        assert ticket["sla_due_at"] is not None
        # .replace("Z", "+00:00"): datetime.fromisoformat() only accepts a
        # trailing "Z" (Zulu/UTC) starting in Python 3.12 — this project
        # targets 3.10 (see pyproject.toml), so the API's ISO-8601 "Z"
        # suffix has to be normalized to an explicit offset before parsing,
        # or this raises `ValueError: Invalid isoformat string`.
        created_at = datetime.fromisoformat(ticket["created_at"].replace("Z", "+00:00"))
        due_at = datetime.fromisoformat(ticket["sla_due_at"].replace("Z", "+00:00"))
        assert due_at - created_at == timedelta(hours=4)
        assert ticket["sla_breached"] is False

    def test_ticket_has_no_due_date_when_no_policy_matches_priority(self, client, db_session):
        # Deliberately seed a policy for a DIFFERENT priority than we'll use,
        # so create_ticket()'s lookup finds nothing and logs a warning
        # instead of setting sla_due_at.
        _seed_sla_policy(db_session, priority="low", resolution_time_hours=72)
        department_id = _get_department_id(db_session)

        register(client, "sla.nopolicy@example.com", "sla_nopolicy", "SLA No Policy")
        token = login(client, "sla.nopolicy@example.com")

        ticket = _create_ticket(client, token, department_id, "critical", "No matching policy")

        assert ticket["sla_due_at"] is None


# =====================================================
# Resolving before/after the due date
# =====================================================


class TestSlaBreachOnResolve:
    def test_resolving_before_due_date_does_not_breach(self, client, db_session):
        _seed_sla_policy(db_session, priority="critical", resolution_time_hours=4)
        department_id = _get_department_id(db_session)

        register(client, "sla.ontime@example.com", "sla_ontime", "SLA On Time")
        reporter_token = login(client, "sla.ontime@example.com")
        ticket = _create_ticket(
            client, reporter_token, department_id, "critical", "Resolved on time"
        )

        engineer = create_active_user(db_session, "engineer", "sla.eng1@example.com", "sla_eng1")
        engineer_token = login(client, "sla.eng1@example.com")

        client.post(
            f"/api/v1/tickets/{ticket['id']}/assign",
            headers=auth_headers(engineer_token),
            json={"assignee_id": engineer.id},
        )

        # sla_due_at is 4 hours out and we resolve immediately — well within SLA.
        resolve_response = client.post(
            f"/api/v1/tickets/{ticket['id']}/resolve", headers=auth_headers(engineer_token)
        )

        assert resolve_response.status_code == 200, resolve_response.text
        resolved = resolve_response.json()
        assert resolved["sla_breached"] is False

    def test_resolving_after_due_date_breaches_and_reflects_in_dashboard(self, client, db_session):
        _seed_sla_policy(db_session, priority="critical", resolution_time_hours=4)
        department_id = _get_department_id(db_session)

        register(client, "sla.late@example.com", "sla_late", "SLA Late")
        reporter_token = login(client, "sla.late@example.com")
        ticket = _create_ticket(client, reporter_token, department_id, "critical", "Resolved late")

        engineer = create_active_user(db_session, "engineer", "sla.eng2@example.com", "sla_eng2")
        engineer_token = login(client, "sla.eng2@example.com")

        client.post(
            f"/api/v1/tickets/{ticket['id']}/assign",
            headers=auth_headers(engineer_token),
            json={"assignee_id": engineer.id},
        )

        # Backdate sla_due_at directly against the DB so resolving "now"
        # is unambiguously late, without needing the test to actually
        # sleep for hours.
        ticket_row = db_session.get(Ticket, ticket["id"])
        ticket_row.sla_due_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db_session.flush()

        resolve_response = client.post(
            f"/api/v1/tickets/{ticket['id']}/resolve", headers=auth_headers(engineer_token)
        )

        assert resolve_response.status_code == 200, resolve_response.text
        resolved = resolve_response.json()
        assert resolved["sla_breached"] is True

        dashboard_response = client.get(
            "/api/v1/dashboard/sla", headers=auth_headers(engineer_token)
        )
        assert dashboard_response.status_code == 200, dashboard_response.text
        stats = {row["department"]: row for row in dashboard_response.json()}

        assert "IT Support" in stats
        it_support = stats["IT Support"]
        assert it_support["total_tickets"] == 1
        assert it_support["breached"] == 1
        assert it_support["breach_rate"] == 100.0


# =====================================================
# Still-open tickets that are already overdue
# (get_sla_stats' "currently overdue" case, without ever resolving)
# =====================================================


class TestSlaCurrentlyOverdue:
    def test_unresolved_overdue_ticket_counts_as_breach_in_dashboard(self, client, db_session):
        _seed_sla_policy(db_session, priority="critical", resolution_time_hours=4)
        department_id = _get_department_id(db_session)

        register(client, "sla.overdue@example.com", "sla_overdue", "SLA Overdue")
        token = login(client, "sla.overdue@example.com")
        ticket = _create_ticket(client, token, department_id, "critical", "Still open and overdue")

        # Never assigned, never resolved — status stays OPEN. Backdate the
        # due date so it's already in the past.
        ticket_row = db_session.get(Ticket, ticket["id"])
        ticket_row.sla_due_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db_session.flush()

        # Need an engineer/admin token to read the dashboard — the reporter
        # here is an employee and can't view it.
        create_active_user(db_session, "engineer", "sla.eng3@example.com", "sla_eng3")
        engineer_token = login(client, "sla.eng3@example.com")

        dashboard_response = client.get(
            "/api/v1/dashboard/sla", headers=auth_headers(engineer_token)
        )
        assert dashboard_response.status_code == 200, dashboard_response.text
        stats = {row["department"]: row for row in dashboard_response.json()}

        assert stats["IT Support"]["total_tickets"] == 1
        assert stats["IT Support"]["breached"] == 1
        assert stats["IT Support"]["breach_rate"] == 100.0
