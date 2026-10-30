"""
Ticket history (audit trail) integration tests.

TicketService rules under test (backend/services/ticket_service.py,
_record_history call sites):
  - Every lifecycle transition (assign, resolve, close, reopen) and every
    update_ticket field change writes a TicketHistory row.
  - Entries come back in chronological order.
  - Same view RBAC as the ticket itself: employees only on their own.
  - A no-op call (e.g. re-assigning to the same engineer while already
    IN_PROGRESS) must not add a spurious entry.
"""

from tests.integration.conftest import auth_headers, create_active_user, login, register


def _create_ticket(client, token: str, title: str = "Monitor flickering") -> dict:
    response = client.post(
        "/api/v1/tickets",
        headers=auth_headers(token),
        json={
            "title": title,
            "description": "Detailed description of the issue, at least 20 characters.",
            "priority": "low",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _get_history(client, token: str, ticket_id: int):
    response = client.get(f"/api/v1/tickets/{ticket_id}/history", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return response.json()


class TestHistoryRecording:
    def test_full_lifecycle_produces_chronological_history(self, client, db_session):
        register(client, "hist.owner1@example.com", "hist_owner1", "Hist Owner1")
        owner_token = login(client, "hist.owner1@example.com")
        ticket = _create_ticket(client, owner_token)
        ticket_id = ticket["id"]

        engineer = create_active_user(db_session, "engineer", "hist.eng1@example.com", "hist_eng1")
        engineer_token = login(client, "hist.eng1@example.com")

        client.post(
            f"/api/v1/tickets/{ticket_id}/assign",
            headers=auth_headers(engineer_token),
            json={"assignee_id": engineer.id},
        )
        client.post(f"/api/v1/tickets/{ticket_id}/resolve", headers=auth_headers(engineer_token))
        client.post(f"/api/v1/tickets/{ticket_id}/close", headers=auth_headers(engineer_token))
        client.post(f"/api/v1/tickets/{ticket_id}/reopen", headers=auth_headers(owner_token))

        history = _get_history(client, owner_token, ticket_id)

        fields = [h["field_changed"] for h in history]
        # assign -> assigned_to_id + status(open->in_progress), resolve ->
        # status, close -> status, reopen -> status = 5 entries total.
        assert fields == ["assigned_to_id", "status", "status", "status", "status"]

        statuses_in_order = [h["new_value"] for h in history if h["field_changed"] == "status"]
        assert statuses_in_order == ["in_progress", "resolved", "closed", "reopened"]

        # Timestamps are non-decreasing (chronological order).
        timestamps = [h["changed_at"] for h in history]
        assert timestamps == sorted(timestamps)

        # changed_by reflects who actually performed each action.
        assert history[0]["changed_by"]["username"] == "hist_eng1"  # assign
        assert history[-1]["changed_by"]["username"] == "hist_owner1"  # reopen

    def test_update_ticket_records_field_level_changes(self, client):
        register(client, "hist.owner2@example.com", "hist_owner2", "Hist Owner2")
        token = login(client, "hist.owner2@example.com")
        ticket = _create_ticket(client, token)

        response = client.patch(
            f"/api/v1/tickets/{ticket['id']}",
            headers=auth_headers(token),
            json={"title": "Updated: monitor flickering constantly now"},
        )
        assert response.status_code == 200, response.text

        history = _get_history(client, token, ticket["id"])

        assert len(history) == 1
        assert history[0]["field_changed"] == "title"
        assert history[0]["old_value"] == "Monitor flickering"
        assert history[0]["new_value"] == "Updated: monitor flickering constantly now"

    def test_no_op_assign_does_not_add_entry(self, client, db_session):
        register(client, "hist.owner3@example.com", "hist_owner3", "Hist Owner3")
        owner_token = login(client, "hist.owner3@example.com")
        ticket = _create_ticket(client, owner_token)
        ticket_id = ticket["id"]

        engineer = create_active_user(db_session, "engineer", "hist.eng2@example.com", "hist_eng2")
        engineer_token = login(client, "hist.eng2@example.com")

        client.post(
            f"/api/v1/tickets/{ticket_id}/assign",
            headers=auth_headers(engineer_token),
            json={"assignee_id": engineer.id},
        )
        first_history = _get_history(client, owner_token, ticket_id)

        # Re-assign to the SAME engineer — already IN_PROGRESS, already
        # assigned to this engineer, so nothing should change.
        client.post(
            f"/api/v1/tickets/{ticket_id}/assign",
            headers=auth_headers(engineer_token),
            json={"assignee_id": engineer.id},
        )
        second_history = _get_history(client, owner_token, ticket_id)

        assert len(second_history) == len(first_history)

    def test_employee_cannot_view_others_ticket_history(self, client):
        register(client, "hist.owner4@example.com", "hist_owner4", "Hist Owner4")
        owner_token = login(client, "hist.owner4@example.com")
        ticket = _create_ticket(client, owner_token)

        register(client, "hist.stranger@example.com", "hist_stranger", "Hist Stranger")
        stranger_token = login(client, "hist.stranger@example.com")

        response = client.get(
            f"/api/v1/tickets/{ticket['id']}/history", headers=auth_headers(stranger_token)
        )

        assert response.status_code == 403

    def test_no_history_for_untouched_ticket(self, client):
        register(client, "hist.owner5@example.com", "hist_owner5", "Hist Owner5")
        token = login(client, "hist.owner5@example.com")
        ticket = _create_ticket(client, token)

        history = _get_history(client, token, ticket["id"])

        assert history == []
