"""
Report export endpoints — CSV, Excel, PDF snapshots of ticket data.

Engineer/admin only: a report is an org-wide view across all tickets,
unlike GET /tickets which restricts employees to their own. All three
formats accept the same filters so a user can preview counts with the
existing ticket list before choosing which format to download.
"""

import io
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from backend.api.deps import get_report_service, require_roles
from backend.models.ticket import TicketPriority, TicketStatus
from backend.services.report_service import ReportService

router = APIRouter()


def _timestamped_filename(extension: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"tickets_report_{stamp}.{extension}"


# =====================================================
# GET /reports/tickets/csv
# =====================================================
@router.get(
    "/tickets/csv",
    summary="Export tickets as CSV",
    description="Streams a CSV snapshot of tickets matching the given filters. "
    "Engineers and admins only.",
    dependencies=[Depends(require_roles("engineer", "admin"))],
)
def export_tickets_csv(
    status: TicketStatus | None = Query(default=None),
    priority: TicketPriority | None = Query(default=None),
    department_id: int | None = Query(default=None, ge=1),
    date_from: date | None = Query(default=None, description="Inclusive start date"),
    date_to: date | None = Query(default=None, description="Inclusive end date"),
    service: ReportService = Depends(get_report_service),
):
    rows = service.get_ticket_rows(status, priority, department_id, date_from, date_to)
    content = service.to_csv_bytes(rows)
    filename = _timestamped_filename("csv")
    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# =====================================================
# GET /reports/tickets/excel
# =====================================================
@router.get(
    "/tickets/excel",
    summary="Export tickets as Excel",
    description="Streams an .xlsx snapshot of tickets matching the given filters. "
    "Engineers and admins only.",
    dependencies=[Depends(require_roles("engineer", "admin"))],
)
def export_tickets_excel(
    status: TicketStatus | None = Query(default=None),
    priority: TicketPriority | None = Query(default=None),
    department_id: int | None = Query(default=None, ge=1),
    date_from: date | None = Query(default=None, description="Inclusive start date"),
    date_to: date | None = Query(default=None, description="Inclusive end date"),
    service: ReportService = Depends(get_report_service),
):
    rows = service.get_ticket_rows(status, priority, department_id, date_from, date_to)
    content = service.to_excel_bytes(rows)
    filename = _timestamped_filename("xlsx")
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# =====================================================
# GET /reports/tickets/pdf
# =====================================================
@router.get(
    "/tickets/pdf",
    summary="Export tickets as PDF",
    description="Streams a formatted PDF snapshot of tickets matching the given filters. "
    "Engineers and admins only.",
    dependencies=[Depends(require_roles("engineer", "admin"))],
)
def export_tickets_pdf(
    status: TicketStatus | None = Query(default=None),
    priority: TicketPriority | None = Query(default=None),
    department_id: int | None = Query(default=None, ge=1),
    date_from: date | None = Query(default=None, description="Inclusive start date"),
    date_to: date | None = Query(default=None, description="Inclusive end date"),
    service: ReportService = Depends(get_report_service),
):
    rows = service.get_ticket_rows(status, priority, department_id, date_from, date_to)
    content = service.to_pdf_bytes(rows)
    filename = _timestamped_filename("pdf")
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
