"""
Comment RBAC integration tests.

CommentService rules under test (backend/services/comment_service.py):
  - Posting/listing requires the same "can view this ticket" check as
    tickets themselves: employees only on their own tickets.
  - Employees can never post an is_internal=True comment (403), even
    on their own ticket.
  - When listing, employees never see internal comments; engineers and
    admins see everything.
"""

from tests.integration.conftest import auth_headers, create_active_user, login, register


def _create_ticket(client, token: str, title: str = "Printer offline") -> dict:
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


def _post_comment(client, token: str, ticket_id: int, body: str, is_internal: bool = False):
    return client.post(
        f"/api/v1/tickets/{ticket_id}/comments",
        headers=auth_headers(token),
        json={"body": body, "is_internal": is_internal},
    )


class TestCommentCreation:
    def test_employee_can_comment_on_own_ticket(self, client):
        register(client, "comment.owner1@example.com", "comment_owner1", "Comment Owner1")
        token = login(client, "comment.owner1@example.com")
        ticket = _create_ticket(client, token)

        response = _post_comment(client, token, ticket["id"], "Still not working, tried a reboot.")

        assert response.status_code == 201, response.text
        comment = response.json()
        assert comment["body"] == "Still not working, tried a reboot."
        assert comment["is_internal"] is False
        assert comment["author"]["username"] == "comment_owner1"

    def test_employee_cannot_post_internal_comment(self, client):
        register(client, "comment.owner2@example.com", "comment_owner2", "Comment Owner2")
        token = login(client, "comment.owner2@example.com")
        ticket = _create_ticket(client, token)

        response = _post_comment(
            client, token, ticket["id"], "Trying to leave an internal note.", is_internal=True
        )

        assert response.status_code == 403
        assert response.json()["error_code"] == "FORBIDDEN"

    def test_employee_cannot_comment_on_others_ticket(self, client):
        register(client, "comment.owner3@example.com", "comment_owner3", "Comment Owner3")
        owner_token = login(client, "comment.owner3@example.com")
        ticket = _create_ticket(client, owner_token)

        register(client, "comment.stranger@example.com", "comment_stranger", "Comment Stranger")
        stranger_token = login(client, "comment.stranger@example.com")

        response = _post_comment(
            client, stranger_token, ticket["id"], "Butting in on someone else's ticket."
        )

        assert response.status_code == 403


class TestCommentVisibility:
    def test_employee_does_not_see_internal_comments(self, client, db_session):
        register(client, "comment.owner4@example.com", "comment_owner4", "Comment Owner4")
        owner_token = login(client, "comment.owner4@example.com")
        ticket = _create_ticket(client, owner_token)

        engineer = create_active_user(
            db_session, "engineer", "comment.eng1@example.com", "comment_eng1"
        )
        engineer_token = login(client, "comment.eng1@example.com")

        # Engineer leaves both a customer-visible reply and an internal note
        _post_comment(client, engineer_token, ticket["id"], "Looking into it.", is_internal=False)
        _post_comment(
            client, engineer_token, ticket["id"], "Root cause: driver conflict.", is_internal=True
        )

        list_response = client.get(
            f"/api/v1/tickets/{ticket['id']}/comments", headers=auth_headers(owner_token)
        )

        assert list_response.status_code == 200, list_response.text
        comments = list_response.json()
        assert len(comments) == 1
        assert comments[0]["body"] == "Looking into it."
        assert comments[0]["is_internal"] is False
        assert engineer.id  # sanity: engineer was actually provisioned

    def test_engineer_sees_internal_comments(self, client, db_session):
        register(client, "comment.owner5@example.com", "comment_owner5", "Comment Owner5")
        owner_token = login(client, "comment.owner5@example.com")
        ticket = _create_ticket(client, owner_token)

        create_active_user(db_session, "engineer", "comment.eng2@example.com", "comment_eng2")
        engineer_token = login(client, "comment.eng2@example.com")

        _post_comment(client, owner_token, ticket["id"], "Any update?", is_internal=False)
        _post_comment(
            client, engineer_token, ticket["id"], "Escalating to network team.", is_internal=True
        )

        list_response = client.get(
            f"/api/v1/tickets/{ticket['id']}/comments", headers=auth_headers(engineer_token)
        )

        assert list_response.status_code == 200, list_response.text
        comments = list_response.json()
        assert len(comments) == 2
        bodies = {c["body"] for c in comments}
        assert bodies == {"Any update?", "Escalating to network team."}
