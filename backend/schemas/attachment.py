"""
Attachment response schema.

There is no "AttachmentCreate" request schema — unlike comments or
tickets, an upload is multipart/form-data (a file, not JSON), so
FastAPI's `UploadFile` is taken directly as an endpoint parameter
instead of being wrapped in a Pydantic model. See
backend/api/v1/endpoints/tickets.py for the upload endpoint.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.schemas.ticket import UserSummary


class AttachmentResponse(BaseModel):
    """Attachment metadata returned after upload or when listing."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    file_name: str
    mime_type: str
    file_size_bytes: int
    uploaded_by: UserSummary
    uploaded_at: datetime
