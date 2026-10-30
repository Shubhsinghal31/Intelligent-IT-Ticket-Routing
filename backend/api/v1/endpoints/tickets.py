"""
Ticket endpoints: create, list, get by ID.

Route handlers are intentionally thin — they delegate all
business logic to TicketService and return shaped responses.
"""

import io

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse

from backend.api.deps import (
    get_attachment_service,
    get_comment_service,
    get_current_active_user,
    get_ticket_service,
)
from backend.models.ticket import TicketPriority, TicketStatus
from backend.models.user import User
from backend.schemas.attachment import AttachmentResponse
from backend.schemas.comment import CommentCreate, CommentResponse
from backend.schemas.common import PaginatedResponse
from backend.schemas.ticket import (
    TicketAssign,
    TicketCreate,
    TicketResponse,
    TicketSummary,
    TicketUpdate,
)
from backend.schemas.ticket_history import TicketHistoryResponse
from backend.services.attachment_service import AttachmentService
from backend.services.comment_service import CommentService
from backend.services.ticket_service import TicketService

router = APIRouter()


# =====================================================
# POST /tickets — create a ticket
# =====================================================
@router.post(
    "",
    response_model=TicketResponse,
    status_code=201,
    summary="Create a new support ticket",
    description="Any authenticated user can raise a ticket. "
    "The reporter is set from the auth token — not the request body.",
)
def create_ticket(
    payload: TicketCreate,
    current_user: User = Depends(get_current_active_user),
    ticket_service: TicketService = Depends(get_ticket_service),
):
    return ticket_service.create_ticket(current_user, payload)


# =====================================================
# GET /tickets — paginated list with filters
# =====================================================
@router.get(
    "",
    response_model=PaginatedResponse[TicketSummary],
    summary="List tickets",
    description="Returns a paginated list of tickets. "
    "Employees see only their own tickets. "
    "Engineers and admins see all tickets.",
)
def list_tickets(
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    status: TicketStatus | None = Query(default=None, description="Filter by status"),
    priority: TicketPriority | None = Query(default=None, description="Filter by priority"),
    department_id: int | None = Query(default=None, ge=1, description="Filter by department"),
    assignee_id: int | None = Query(default=None, ge=1, description="Filter by assignee"),
    current_user: User = Depends(get_current_active_user),
    ticket_service: TicketService = Depends(get_ticket_service),
):
    result = ticket_service.get_tickets(
        requesting_user=current_user,
        page=page,
        page_size=page_size,
        status=status,
        priority=priority,
        department_id=department_id,
        assignee_id=assignee_id,
    )
    return PaginatedResponse[TicketSummary](**result)


# =====================================================
# GET /tickets/{ticket_id} — single ticket detail
# =====================================================
@router.get(
    "/{ticket_id}",
    response_model=TicketResponse,
    summary="Get ticket by ID",
    description="Returns full ticket detail. " "Employees can only view their own tickets.",
)
def get_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_active_user),
    ticket_service: TicketService = Depends(get_ticket_service),
):
    return ticket_service.get_ticket(ticket_id, current_user)


# =====================================================
# PATCH /tickets/{ticket_id} — partial field update
# =====================================================
@router.patch(
    "/{ticket_id}",
    response_model=TicketResponse,
    summary="Update ticket fields",
    description="Partial update — only provided fields are changed. "
    "Status cannot be changed here; use lifecycle endpoints.",
)
def update_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    current_user: User = Depends(get_current_active_user),
    ticket_service: TicketService = Depends(get_ticket_service),
):
    return ticket_service.update_ticket(ticket_id, current_user, payload)


# =====================================================
# POST /tickets/{ticket_id}/assign
# =====================================================
@router.post(
    "/{ticket_id}/assign",
    response_model=TicketResponse,
    summary="Assign ticket to an engineer",
    description="Sets the assignee and transitions status to IN_PROGRESS if currently OPEN. "
    "Engineers and admins only.",
)
def assign_ticket(
    ticket_id: int,
    payload: TicketAssign,
    current_user: User = Depends(get_current_active_user),
    ticket_service: TicketService = Depends(get_ticket_service),
):
    return ticket_service.assign_ticket(ticket_id, current_user, payload.assignee_id)


# =====================================================
# POST /tickets/{ticket_id}/close
# =====================================================
@router.post(
    "/{ticket_id}/close",
    response_model=TicketResponse,
    summary="Close a resolved ticket",
    description="Transitions status from RESOLVED → CLOSED and sets closed_at. "
    "Engineers and admins only.",
)
def close_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_active_user),
    ticket_service: TicketService = Depends(get_ticket_service),
):
    return ticket_service.close_ticket(ticket_id, current_user)


# =====================================================
# POST /tickets/{ticket_id}/reopen
# =====================================================
@router.post(
    "/{ticket_id}/reopen",
    response_model=TicketResponse,
    summary="Reopen a closed or resolved ticket",
    description="Transitions status to REOPENED. Clears closed_at and resolved_at. "
    "Reporters can reopen their own tickets; engineers and admins can reopen any.",
)
def reopen_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_active_user),
    ticket_service: TicketService = Depends(get_ticket_service),
):
    return ticket_service.reopen_ticket(ticket_id, current_user)


# =====================================================
# POST /tickets/{ticket_id}/resolve
# =====================================================
@router.post(
    "/{ticket_id}/resolve",
    response_model=TicketResponse,
    summary="Mark ticket as resolved",
    description="Transitions status to RESOLVED and sets resolved_at. "
    "Valid from IN_PROGRESS or REOPENED. Engineers and admins only.",
)
def resolve_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_active_user),
    ticket_service: TicketService = Depends(get_ticket_service),
):
    return ticket_service.resolve_ticket(ticket_id, current_user)


# =====================================================
# POST /tickets/{ticket_id}/comments
# =====================================================
@router.post(
    "/{ticket_id}/comments",
    response_model=CommentResponse,
    status_code=201,
    summary="Add a comment to a ticket",
    description="Any user who can view the ticket can comment. "
    "Internal comments are restricted to engineers and admins.",
)
def create_comment(
    ticket_id: int,
    payload: CommentCreate,
    current_user: User = Depends(get_current_active_user),
    comment_service: CommentService = Depends(get_comment_service),
):
    return comment_service.create_comment(ticket_id, current_user, payload)


# =====================================================
# GET /tickets/{ticket_id}/comments
# =====================================================
@router.get(
    "/{ticket_id}/comments",
    response_model=list[CommentResponse],
    summary="List comments on a ticket",
    description="Employees see only non-internal comments on their own tickets. "
    "Engineers and admins see all comments including internal notes.",
)
def list_comments(
    ticket_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
    comment_service: CommentService = Depends(get_comment_service),
):
    return comment_service.get_comments(ticket_id, current_user, page, page_size)


# =====================================================
# POST /tickets/{ticket_id}/attachments
# =====================================================
@router.post(
    "/{ticket_id}/attachments",
    response_model=AttachmentResponse,
    status_code=201,
    summary="Upload a file attachment to a ticket",
    description="Any user who can view the ticket can attach a file. "
    "Allowed types and the size limit are enforced server-side "
    "(see ATTACHMENTS_ALLOWED_MIME_TYPES / ATTACHMENTS_MAX_SIZE_BYTES).",
)
def upload_attachment(
    ticket_id: int,
    file: UploadFile = File(..., description="File to attach (max 10 MB)"),
    current_user: User = Depends(get_current_active_user),
    attachment_service: AttachmentService = Depends(get_attachment_service),
):
    content = file.file.read()
    return attachment_service.upload_attachment(
        ticket_id,
        current_user,
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        content=content,
    )


# =====================================================
# GET /tickets/{ticket_id}/attachments
# =====================================================
@router.get(
    "/{ticket_id}/attachments",
    response_model=list[AttachmentResponse],
    summary="List attachments on a ticket",
    description="Employees can only list attachments on their own tickets. "
    "Engineers and admins can list attachments on any ticket.",
)
def list_attachments(
    ticket_id: int,
    current_user: User = Depends(get_current_active_user),
    attachment_service: AttachmentService = Depends(get_attachment_service),
):
    return attachment_service.get_attachments(ticket_id, current_user)


# =====================================================
# GET /tickets/{ticket_id}/attachments/{attachment_id}/download
# =====================================================
@router.get(
    "/{ticket_id}/attachments/{attachment_id}/download",
    summary="Download an attachment's file content",
    description="Streams the raw file bytes with the original filename. "
    "Served via an authenticated endpoint rather than a static file "
    "mount, so the same RBAC as the rest of the ticket applies.",
)
def download_attachment(
    ticket_id: int,
    attachment_id: int,
    current_user: User = Depends(get_current_active_user),
    attachment_service: AttachmentService = Depends(get_attachment_service),
):
    content, attachment = attachment_service.get_attachment_file(
        ticket_id, attachment_id, current_user
    )
    return StreamingResponse(
        io.BytesIO(content),
        media_type=attachment.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{attachment.file_name}"'},
    )


# =====================================================
# GET /tickets/{ticket_id}/history
# =====================================================
@router.get(
    "/{ticket_id}/history",
    response_model=list[TicketHistoryResponse],
    summary="Get a ticket's audit trail",
    description="Returns every tracked field change (status, priority, "
    "assignee, department, title, description) in chronological order. "
    "Same view rule as the ticket itself: employees only on their own tickets.",
)
def get_ticket_history(
    ticket_id: int,
    current_user: User = Depends(get_current_active_user),
    ticket_service: TicketService = Depends(get_ticket_service),
):
    return ticket_service.get_history(ticket_id, current_user)
