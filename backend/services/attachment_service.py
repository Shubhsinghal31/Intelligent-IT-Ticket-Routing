"""
Attachment business logic — upload, list, and download ticket files.

Storage design (local disk, see backend/core/config.py ATTACHMENTS_*):
  - Files live under settings.ATTACHMENTS_STORAGE_PATH, one subfolder per
    ticket ID, e.g. uploads/attachments/42/<uuid>.png.
  - The on-disk filename is always a fresh UUID, never the client-supplied
    filename. Two reasons: (1) path traversal — a filename like
    "../../etc/passwd" must never reach the filesystem layer, and
    generating our own name sidesteps the whole class of bug rather than
    trying to sanitize every possible attack string; (2) collisions — two
    users uploading "screenshot.png" to the same ticket would otherwise
    overwrite each other.
  - The client-supplied filename is preserved separately in
    Attachment.file_name purely for display/download purposes.
  - Attachment.file_path stores a path RELATIVE to the storage root, not
    absolute. That is what makes swapping to S3-compatible storage later
    a one-file change (this service) instead of a data migration: relative
    paths double as S3 keys unchanged.

Note this module intentionally takes raw `bytes` + `filename` +
`content_type` rather than FastAPI's `UploadFile` — the service layer
should not depend on the web framework, matching CommentService/
TicketService, which also take plain schema/primitive arguments. The
endpoint (backend/api/v1/endpoints/tickets.py) is the only place that
touches UploadFile; it reads the bytes and hands them off here.
"""

import uuid
from pathlib import Path

from loguru import logger
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.exceptions import ForbiddenException, NotFoundException, ValidationException
from backend.models.attachment import Attachment
from backend.models.ticket import Ticket
from backend.models.user import User
from backend.repositories.attachment_repository import AttachmentRepository
from backend.repositories.ticket_repository import TicketRepository


class AttachmentService:
    """Encapsulates attachment upload/list/download workflows."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.attachment_repo = AttachmentRepository(db)
        self.ticket_repo = TicketRepository(db)

    def _get_ticket_or_404(self, ticket_id: int) -> Ticket:
        ticket = self.ticket_repo.get_by_id(ticket_id)
        if not ticket:
            raise NotFoundException(f"Ticket {ticket_id} not found")
        return ticket

    def _assert_can_view(self, ticket: Ticket, user: User) -> None:
        """Same rule as CommentService: employees only on their own tickets."""
        if user.role.name == "employee" and ticket.created_by_id != user.id:
            raise ForbiddenException("You can only access attachments on your own tickets")

    # =====================================================
    # Upload
    # =====================================================

    def upload_attachment(
        self,
        ticket_id: int,
        user: User,
        *,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> Attachment:
        """
        Validate and store an uploaded file, then record it in the DB.

        Raises:
            NotFoundException: Ticket doesn't exist.
            ForbiddenException: Employee uploading to someone else's ticket.
            ValidationException: Disallowed MIME type, empty file, or file
                too large (mirrors the DB CHECK constraints so a bad
                upload gets a clear 422 instead of a raw IntegrityError).
        """
        ticket = self._get_ticket_or_404(ticket_id)
        self._assert_can_view(ticket, user)

        if content_type not in settings.ATTACHMENTS_ALLOWED_MIME_TYPES:
            raise ValidationException(
                f"File type '{content_type}' is not allowed. "
                f"Allowed types: {', '.join(settings.ATTACHMENTS_ALLOWED_MIME_TYPES)}"
            )

        size = len(content)
        if size == 0:
            raise ValidationException("Uploaded file is empty")
        if size > settings.ATTACHMENTS_MAX_SIZE_BYTES:
            max_mb = settings.ATTACHMENTS_MAX_SIZE_BYTES / (1024 * 1024)
            raise ValidationException(f"File exceeds the {max_mb:.0f} MB upload limit")

        # Safe on-disk name: fresh UUID + original extension only (never the
        # client-supplied stem). suffix is taken from the *original* name
        # purely so the file has a sensible extension if downloaded outside
        # the app; it plays no role in path resolution.
        extension = Path(filename).suffix
        safe_filename = f"{uuid.uuid4().hex}{extension}"
        relative_path = f"{ticket_id}/{safe_filename}"

        full_path = settings.attachments_storage_full_path / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)

        attachment = Attachment(
            ticket_id=ticket_id,
            uploaded_by_id=user.id,
            file_name=filename,
            file_path=relative_path,
            mime_type=content_type,
            file_size_bytes=size,
        )
        self.attachment_repo.add(attachment)
        self.attachment_repo.commit()
        self.db.refresh(attachment)

        logger.info(
            f"Attachment uploaded: id={attachment.id} "
            f"ticket_id={ticket_id} "
            f"uploaded_by_id={user.id} "
            f"size={size}"
        )
        return attachment

    # =====================================================
    # List
    # =====================================================

    def get_attachments(self, ticket_id: int, user: User) -> list[Attachment]:
        """Return all attachments for a ticket, with RBAC applied."""
        ticket = self._get_ticket_or_404(ticket_id)
        self._assert_can_view(ticket, user)
        return self.attachment_repo.get_by_ticket(ticket_id)

    # =====================================================
    # Download
    # =====================================================

    def get_attachment_file(
        self, ticket_id: int, attachment_id: int, user: User
    ) -> tuple[bytes, Attachment]:
        """
        Load an attachment's bytes from disk, with RBAC applied.

        Raises:
            NotFoundException: Ticket/attachment doesn't exist, the
                attachment doesn't belong to this ticket, or the DB row
                exists but the file is missing from disk (e.g. manual
                deletion, or — on Render — a redeploy that wiped the
                ephemeral filesystem; see the ATTACHMENTS_STORAGE_PATH
                comment in backend/core/config.py).
            ForbiddenException: Employee accessing someone else's ticket.
        """
        ticket = self._get_ticket_or_404(ticket_id)
        self._assert_can_view(ticket, user)

        attachment = self.attachment_repo.get_by_id(attachment_id)
        if not attachment or attachment.ticket_id != ticket_id:
            raise NotFoundException(f"Attachment {attachment_id} not found on this ticket")

        full_path = settings.attachments_storage_full_path / attachment.file_path
        if not full_path.is_file():
            logger.error(f"Attachment file missing from disk: id={attachment.id} path={full_path}")
            raise NotFoundException("Attachment file is no longer available in storage")

        return full_path.read_bytes(), attachment
