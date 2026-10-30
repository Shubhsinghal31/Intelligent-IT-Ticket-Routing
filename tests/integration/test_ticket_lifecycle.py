"""
Ticket lifecycle end-to-end: create -> assign -> resolve -> close -> reopen,
plus RBAC denials, through real HTTP requests against a real Postgres.

Shared provisioning/auth helpers (create_active_user, login, auth_headers,
register) now live in tests/integration/conftest.py — every integration
test file that needs a non-employee user or a token uses the same ones
instead of each file keeping its own copy.
"""

from tests.integration.conftest import (
    auth_headers,
    create_active_user,
    login,
    register,
)

# =====================================================
# Helper local to this file only
# =====================================================


def _create_ticket(client, token: str, title: str = "VPN not connecting") -> dict:
    response = client.post(
        "/api/v1/tickets",
        headers=auth_headers(token),
        json={
            "title": title,
            "description": "Detailed description of the issue, at least 20 characters.",
            "priority": "medium",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


# =====================================================
# Full happy-path lifecycle
# =====================================================


class TestTicketLifecycle:
    def test_full_lifecycle_create_assign_resolve_close_reopen(self, client, db_session):
        register(
            client, "lifecycle.employee@example.com", "lifecycle_employee", "Lifecycle Employee"
        )
        employee_token = login(client, "lifecycle.employee@example.com")

        ticket = _create_ticket(client, employee_token)
        assert ticket["status"] == "open"
        assert ticket["assignee"] is None
        ticket_id = ticket["id"]

        engineer = create_active_user(
            db_session, "engineer", "lifecycle.engineer@example.com", "lifecycle_engineer"
        )
        engineer_token = login(client, "lifecycle.engineer@example.com")

        assign_response = client.post(
            f"/api/v1/tickets/{ticket_id}/assign",
            headers=auth_headers(engineer_token),
            json={"assignee_id": engineer.id},
        )
        assert assign_response.status_code == 200, assign_response.text
        assigned = assign_response.json()
        assert assigned["status"] == "in_progress"
        assert assigned["assignee"]["id"] == engineer.id

        resolve_response = client.post(
            f"/api/v1/tickets/{ticket_id}/resolve", headers=auth_headers(engineer_token)
        )
        assert resolve_response.status_code == 200, resolve_response.text
        resolved = resolve_response.json()
        assert resolved["status"] == "resolved"
        assert resolved["resolved_at"] is not None

        close_response = client.post(
            f"/api/v1/tickets/{ticket_id}/close", headers=auth_headers(engineer_token)
        )
        assert close_response.status_code == 200, close_response.text
        closed = close_response.json()
        assert closed["status"] == "closed"
        assert closed["closed_at"] is not None

        reopen_response = client.post(
            f"/api/v1/tickets/{ticket_id}/reopen", headers=auth_headers(employee_token)
        )
        assert reopen_response.status_code == 200, reopen_response.text
        reopened = reopen_response.json()
        assert reopened["status"] == "reopened"
        assert reopened["closed_at"] is None
        assert reopened["resolved_at"] is None


# =====================================================
# RBAC denials
# =====================================================


class TestTicketRBAC:
    def test_employee_cannot_assign_ticket(self, client, db_session):
        register(client, "rbac.assign@example.com", "rbac_assign", "RBAC Assign")
        token = login(client, "rbac.assign@example.com")
        ticket = _create_ticket(client, token)

        response = client.post(
            f"/api/v1/tickets/{ticket['id']}/assign",
            headers=auth_headers(token),
            json={"assignee_id": 1},
        )

        assert response.status_code == 403
        assert response.json()["error_code"] == "FORBIDDEN"

    def test_employee_cannot_resolve_ticket(self, client):
        register(client, "rbac.resolve@example.com", "rbac_resolve", "RBAC Resolve")
        token = login(client, "rbac.resolve@example.com")
        ticket = _create_ticket(client, token)

        response = client.post(
            f"/api/v1/tickets/{ticket['id']}/resolve", headers=auth_headers(token)
        )

        assert response.status_code == 403

    def test_employee_cannot_close_ticket(self, client):
        register(client, "rbac.close@example.com", "rbac_close", "RBAC Close")
        token = login(client, "rbac.close@example.com")
        ticket = _create_ticket(client, token)

        response = client.post(f"/api/v1/tickets/{ticket['id']}/close", headers=auth_headers(token))

        assert response.status_code == 403

    def test_employee_cannot_view_others_ticket(self, client):
        register(client, "rbac.owner@example.com", "rbac_owner", "RBAC Owner")
        owner_token = login(client, "rbac.owner@example.com")
        ticket = _create_ticket(client, owner_token)

        register(client, "rbac.other@example.com", "rbac_other", "RBAC Other")
        other_token = login(client, "rbac.other@example.com")

        response = client.get(f"/api/v1/tickets/{ticket['id']}", headers=auth_headers(other_token))

        assert response.status_code == 403


# =====================================================
# State-machine rules (not just role checks)
# =====================================================


class TestTicketStateTransitions:
    def test_cannot_resolve_a_ticket_that_is_still_open(self, client, db_session):
        register(client, "state.reporter@example.com", "state_reporter", "State Reporter")
        reporter_token = login(client, "state.reporter@example.com")
        ticket = _create_ticket(client, reporter_token)

        create_active_user(db_session, "engineer", "state.engineer@example.com", "state_engineer")
        engineer_token = login(client, "state.engineer@example.com")

        response = client.post(
            f"/api/v1/tickets/{ticket['id']}/resolve", headers=auth_headers(engineer_token)
        )

        assert response.status_code == 403
        assert "IN_PROGRESS or REOPENED" in response.json()["detail"]

    def test_cannot_close_a_ticket_that_is_not_resolved(self, client, db_session):
        register(client, "state2.reporter@example.com", "state2_reporter", "State2 Reporter")
        reporter_token = login(client, "state2.reporter@example.com")
        ticket = _create_ticket(client, reporter_token)

        engineer = create_active_user(
            db_session, "engineer", "state2.engineer@example.com", "state2_engineer"
        )
        engineer_token = login(client, "state2.engineer@example.com")

        client.post(
            f"/api/v1/tickets/{ticket['id']}/assign",
            headers=auth_headers(engineer_token),
            json={"assignee_id": engineer.id},
        )

        response = client.post(
            f"/api/v1/tickets/{ticket['id']}/close", headers=auth_headers(engineer_token)
        )

        assert response.status_code == 403
        assert "RESOLVED" in response.json()["detail"]
