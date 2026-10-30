"""
Unit tests for AttachmentService business logic.

Unlike the other unit-test files in this directory (CommentService,
TicketService, ...), a handful of tests here do touch the real
filesystem — via pytest's `tmp_path` fixture, monkeypatched onto
settings.ATTACHMENTS_STORAGE_PATH. That's a deliberate exception, not a
drift from convention: upload/download's entire job is reading and
writing files, so a test that stubs the filesystem away wouldn't be
testing anything. tmp_path is pytest's standard tool for exactly this
— a fresh, auto-cleaned-up directory per test, so it stays as hermetic
as the fully-mocked tests elsewhere in this file.
"""

from unittest.mock import MagicMock

import pytest

from backend.core.config import settings
from backend.core.exceptions import ForbiddenException, NotFoundException, ValidationException
from backend.models.attachment import Attachment
from backend.services.attachment_service import AttachmentService


def make_service():
    db = MagicMock()
    service = AttachmentService(db)
    service.attachment_repo = MagicMock()
    service.ticket_repo = MagicMock()
    return service


ALLOWED_CONTENT_TYPE = "text/plain"


class TestUploadAttachment:

    def test_raises_404_for_missing_ticket(self, employee_user):
        service = make_service()
        service.ticket_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundException):
            service.upload_attachment(
                999,
                employee_user,
                filename="notes.txt",
                content_type=ALLOWED_CONTENT_TYPE,
                content=b"hello",
            )

    def test_employee_cannot_upload_to_others_ticket(self, employee_user, open_ticket):
        open_ticket.created_by_id = 999  # not employee's ticket
        service = make_service()
        service.ticket_repo.get_by_id.return_value = open_ticket

        with pytest.raises(ForbiddenException, match="your own tickets"):
            service.upload_attachment(
                open_ticket.id,
                employee_user,
                filename="notes.txt",
                content_type=ALLOWED_CONTENT_TYPE,
                content=b"hello",
            )

    def test_rejects_disallowed_mime_type(self, employee_user, open_ticket):
        service = make_service()
        service.ticket_repo.get_by_id.return_value = open_ticket

        with pytest.raises(ValidationException, match="not allowed"):
            service.upload_attachment(
                open_ticket.id,
                employee_user,
                filename="malware.exe",
                content_type="application/x-msdownload",
                content=b"hello",
            )

    def test_rejects_empty_file(self, employee_user, open_ticket):
        service = make_service()
        service.ticket_repo.get_by_id.return_value = open_ticket

        with pytest.raises(ValidationException, match="empty"):
            service.upload_attachment(
                open_ticket.id,
                employee_user,
                filename="empty.txt",
                content_type=ALLOWED_CONTENT_TYPE,
                content=b"",
            )

    def test_rejects_oversized_file(self, employee_user, open_ticket, monkeypatch):
        monkeypatch.setattr(settings, "ATTACHMENTS_MAX_SIZE_BYTES", 10)
        service = make_service()
        service.ticket_repo.get_by_id.return_value = open_ticket

        with pytest.raises(ValidationException, match="exceeds"):
            service.upload_attachment(
                open_ticket.id,
                employee_user,
                filename="too_big.txt",
                content_type=ALLOWED_CONTENT_TYPE,
                content=b"x" * 100,
            )

    def test_uploads_successfully_and_writes_file(
        self, employee_user, open_ticket, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(settings, "ATTACHMENTS_STORAGE_PATH", str(tmp_path))
        service = make_service()
        service.ticket_repo.get_by_id.return_value = open_ticket
        service.db.refresh.return_value = None

        service.upload_attachment(
            open_ticket.id,
            employee_user,
            filename="notes.txt",
            content_type=ALLOWED_CONTENT_TYPE,
            content=b"hello world",
        )

        assert service.attachment_repo.add.call_count == 1
        saved: Attachment = service.attachment_repo.add.call_args[0][0]
        assert saved.ticket_id == open_ticket.id
        assert saved.uploaded_by_id == employee_user.id
        assert saved.file_name == "notes.txt"
        assert saved.mime_type == ALLOWED_CONTENT_TYPE
        assert saved.file_size_bytes == len(b"hello world")
        # file_path is relative ("<ticket_id>/<uuid>.txt") — never absolute.
        assert saved.file_path.startswith(f"{open_ticket.id}/")
        assert saved.file_path.endswith(".txt")

        # And the bytes actually landed on disk at that relative path.
        written = (tmp_path / saved.file_path).read_bytes()
        assert written == b"hello world"

        service.attachment_repo.commit.assert_called_once()


class TestGetAttachments:

    def test_employee_can_list_own_ticket_attachments(self, employee_user, open_ticket):
        service = make_service()
        service.ticket_repo.get_by_id.return_value = open_ticket
        service.attachment_repo.get_by_ticket.return_value = []

        service.get_attachments(open_ticket.id, employee_user)

        service.attachment_repo.get_by_ticket.assert_called_once_with(open_ticket.id)

    def test_employee_cannot_list_others_ticket_attachments(self, employee_user, open_ticket):
        open_ticket.created_by_id = 999
        service = make_service()
        service.ticket_repo.get_by_id.return_value = open_ticket

        with pytest.raises(ForbiddenException):
            service.get_attachments(open_ticket.id, employee_user)


class TestGetAttachmentFile:

    def _make_attachment(self, ticket_id: int, file_path: str) -> Attachment:
        attachment = MagicMock(spec=Attachment)
        attachment.id = 5
        attachment.ticket_id = ticket_id
        attachment.file_path = file_path
        attachment.file_name = "notes.txt"
        attachment.mime_type = ALLOWED_CONTENT_TYPE
        return attachment

    def test_raises_404_when_attachment_not_found(self, employee_user, open_ticket):
        service = make_service()
        service.ticket_repo.get_by_id.return_value = open_ticket
        service.attachment_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundException):
            service.get_attachment_file(open_ticket.id, 5, employee_user)

    def test_raises_404_when_attachment_belongs_to_different_ticket(
        self, employee_user, open_ticket
    ):
        service = make_service()
        service.ticket_repo.get_by_id.return_value = open_ticket
        service.attachment_repo.get_by_id.return_value = self._make_attachment(
            ticket_id=999, file_path="999/x.txt"
        )

        with pytest.raises(NotFoundException):
            service.get_attachment_file(open_ticket.id, 5, employee_user)

    def test_raises_404_when_file_missing_from_disk(
        self, employee_user, open_ticket, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(settings, "ATTACHMENTS_STORAGE_PATH", str(tmp_path))
        service = make_service()
        service.ticket_repo.get_by_id.return_value = open_ticket
        service.attachment_repo.get_by_id.return_value = self._make_attachment(
            ticket_id=open_ticket.id, file_path=f"{open_ticket.id}/does_not_exist.txt"
        )

        with pytest.raises(NotFoundException, match="no longer available"):
            service.get_attachment_file(open_ticket.id, 5, employee_user)

    def test_returns_bytes_when_file_exists(
        self, employee_user, open_ticket, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(settings, "ATTACHMENTS_STORAGE_PATH", str(tmp_path))
        relative_path = f"{open_ticket.id}/existing.txt"
        full_path = tmp_path / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(b"stored content")

        service = make_service()
        service.ticket_repo.get_by_id.return_value = open_ticket
        service.attachment_repo.get_by_id.return_value = self._make_attachment(
            ticket_id=open_ticket.id, file_path=relative_path
        )

        content, attachment = service.get_attachment_file(open_ticket.id, 5, employee_user)

        assert content == b"stored content"
        assert attachment.file_path == relative_path

    def test_employee_cannot_download_others_ticket_attachment(self, employee_user, open_ticket):
        open_ticket.created_by_id = 999
        service = make_service()
        service.ticket_repo.get_by_id.return_value = open_ticket

        with pytest.raises(ForbiddenException):
            service.get_attachment_file(open_ticket.id, 5, employee_user)
