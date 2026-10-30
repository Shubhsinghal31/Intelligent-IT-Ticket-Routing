"""
Attachment upload/list/download integration tests.

AttachmentService rules under test (backend/services/attachment_service.py):
  - Upload/list/download all require the same "can view this ticket" check
    used by comments: employees only on their own tickets.
  - Uploads are rejected (422) for disallowed MIME types, empty files, and
    files over the configured size limit.
  - A successful upload is retrievable byte-for-byte via the download
    endpoint, with the original filename and content-type preserved.

Storage is redirected to a pytest tmp_path for the whole test module (see
the autouse `_use_tmp_storage` fixture below) so this suite never writes
into the project's real uploads/ directory.
"""

import io

import pytest

from backend.core.config import settings
from tests.integration.conftest import auth_headers, create_active_user, login, register


@pytest.fixture(autouse=True)
def _use_tmp_storage(tmp_path, monkeypatch):
    """Redirect attachment storage to a throwaway directory for this suite."""
    monkeypatch.setattr(settings, "ATTACHMENTS_STORAGE_PATH", str(tmp_path))


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


def _upload(client, token: str, ticket_id: int, filename: str, content: bytes, content_type: str):
    return client.post(
        f"/api/v1/tickets/{ticket_id}/attachments",
        headers=auth_headers(token),
        files={"file": (filename, io.BytesIO(content), content_type)},
    )


class TestAttachmentUpload:
    def test_owner_can_upload_to_own_ticket(self, client):
        register(client, "attach.owner1@example.com", "attach_owner1", "Attach Owner1")
        token = login(client, "attach.owner1@example.com")
        ticket = _create_ticket(client, token)

        response = _upload(
            client, token, ticket["id"], "log.txt", b"error trace here", "text/plain"
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["file_name"] == "log.txt"
        assert body["mime_type"] == "text/plain"
        assert body["file_size_bytes"] == len(b"error trace here")
        assert body["uploaded_by"]["username"] == "attach_owner1"

    def test_employee_cannot_upload_to_others_ticket(self, client):
        register(client, "attach.owner2@example.com", "attach_owner2", "Attach Owner2")
        owner_token = login(client, "attach.owner2@example.com")
        ticket = _create_ticket(client, owner_token)

        register(client, "attach.stranger@example.com", "attach_stranger", "Attach Stranger")
        stranger_token = login(client, "attach.stranger@example.com")

        response = _upload(
            client, stranger_token, ticket["id"], "log.txt", b"snooping", "text/plain"
        )

        assert response.status_code == 403

    def test_rejects_disallowed_mime_type(self, client):
        register(client, "attach.owner3@example.com", "attach_owner3", "Attach Owner3")
        token = login(client, "attach.owner3@example.com")
        ticket = _create_ticket(client, token)

        response = _upload(
            client,
            token,
            ticket["id"],
            "virus.exe",
            b"MZ\x90\x00",
            "application/x-msdownload",
        )

        assert response.status_code == 422
        assert response.json()["error_code"] == "VALIDATION_ERROR"

    def test_rejects_empty_file(self, client):
        register(client, "attach.owner4@example.com", "attach_owner4", "Attach Owner4")
        token = login(client, "attach.owner4@example.com")
        ticket = _create_ticket(client, token)

        response = _upload(client, token, ticket["id"], "empty.txt", b"", "text/plain")

        assert response.status_code == 422

    def test_rejects_oversized_file(self, client, monkeypatch):
        monkeypatch.setattr(settings, "ATTACHMENTS_MAX_SIZE_BYTES", 10)
        register(client, "attach.owner5@example.com", "attach_owner5", "Attach Owner5")
        token = login(client, "attach.owner5@example.com")
        ticket = _create_ticket(client, token)

        response = _upload(client, token, ticket["id"], "big.txt", b"x" * 100, "text/plain")

        assert response.status_code == 422

    def test_engineer_can_upload_to_any_ticket(self, client, db_session):
        register(client, "attach.owner6@example.com", "attach_owner6", "Attach Owner6")
        owner_token = login(client, "attach.owner6@example.com")
        ticket = _create_ticket(client, owner_token)

        create_active_user(db_session, "engineer", "attach.eng1@example.com", "attach_eng1")
        engineer_token = login(client, "attach.eng1@example.com")

        response = _upload(
            client, engineer_token, ticket["id"], "diagnosis.txt", b"root cause found", "text/plain"
        )

        assert response.status_code == 201, response.text


class TestAttachmentListAndDownload:
    def test_list_and_download_round_trip(self, client):
        register(client, "attach.owner7@example.com", "attach_owner7", "Attach Owner7")
        token = login(client, "attach.owner7@example.com")
        ticket = _create_ticket(client, token)

        upload_response = _upload(
            client, token, ticket["id"], "report.csv", b"col1,col2\n1,2\n", "text/csv"
        )
        attachment_id = upload_response.json()["id"]

        list_response = client.get(
            f"/api/v1/tickets/{ticket['id']}/attachments", headers=auth_headers(token)
        )
        assert list_response.status_code == 200, list_response.text
        items = list_response.json()
        assert len(items) == 1
        assert items[0]["file_name"] == "report.csv"

        download_response = client.get(
            f"/api/v1/tickets/{ticket['id']}/attachments/{attachment_id}/download",
            headers=auth_headers(token),
        )
        assert download_response.status_code == 200
        assert download_response.content == b"col1,col2\n1,2\n"
        assert "report.csv" in download_response.headers["content-disposition"]

    def test_employee_cannot_list_others_ticket_attachments(self, client):
        register(client, "attach.owner8@example.com", "attach_owner8", "Attach Owner8")
        owner_token = login(client, "attach.owner8@example.com")
        ticket = _create_ticket(client, owner_token)
        _upload(client, owner_token, ticket["id"], "notes.txt", b"private", "text/plain")

        register(client, "attach.stranger2@example.com", "attach_stranger2", "Attach Stranger2")
        stranger_token = login(client, "attach.stranger2@example.com")

        response = client.get(
            f"/api/v1/tickets/{ticket['id']}/attachments", headers=auth_headers(stranger_token)
        )

        assert response.status_code == 403

    def test_download_404_for_attachment_on_different_ticket(self, client):
        register(client, "attach.owner9@example.com", "attach_owner9", "Attach Owner9")
        token = login(client, "attach.owner9@example.com")
        ticket_a = _create_ticket(client, token, title="Ticket A issue")
        ticket_b = _create_ticket(client, token, title="Ticket B issue")

        upload_response = _upload(
            client, token, ticket_a["id"], "a_only.txt", b"belongs to A", "text/plain"
        )
        attachment_id = upload_response.json()["id"]

        response = client.get(
            f"/api/v1/tickets/{ticket_b['id']}/attachments/{attachment_id}/download",
            headers=auth_headers(token),
        )

        assert response.status_code == 404
