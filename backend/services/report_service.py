"""
Report generation service.

Fetches ticket data (via TicketRepository.get_all_filtered — unpaginated,
see Milestone 9 addition there) and renders it into CSV, Excel, and PDF
bytes. Rendering is kept in this service rather than the route layer so
it's unit-testable without a running FastAPI app or database.
"""

from __future__ import annotations

import io
from datetime import date, datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from backend.models.ticket import Ticket, TicketPriority, TicketStatus
from backend.repositories.ticket_repository import TicketRepository

# Column order shared by all three export formats, so CSV/Excel/PDF
# always agree on what a "ticket report row" looks like.
REPORT_COLUMNS = [
    "Ticket Number",
    "Title",
    "Status",
    "Priority",
    "Department",
    "Reporter",
    "Assignee",
    "Created At",
    "Resolved At",
    "SLA Breached",
]


class ReportService:
    """Builds tabular ticket reports and renders them as CSV/Excel/PDF bytes."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.ticket_repo = TicketRepository(db)

    # =====================================================
    # Data — fetch + flatten
    # =====================================================

    def get_ticket_rows(
        self,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        department_id: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict]:
        """
        Fetch matching tickets and flatten each into a plain dict row.

        Flattening here (rather than in the renderers) means to_csv_bytes/
        to_excel_bytes/to_pdf_bytes never touch an ORM object — they only
        ever see plain dicts, which keeps them trivially unit-testable.
        """
        tickets = self.ticket_repo.get_all_filtered(
            status=status,
            priority=priority,
            department_id=department_id,
            date_from=date_from,
            date_to=date_to,
        )
        return [self._flatten(t) for t in tickets]

    def _flatten(self, ticket: Ticket) -> dict:
        return {
            "Ticket Number": ticket.ticket_number,
            "Title": ticket.title,
            "Status": ticket.status.value,
            "Priority": ticket.priority.value,
            "Department": ticket.department.name if ticket.department else "Unassigned",
            "Reporter": ticket.reporter.full_name if ticket.reporter else "",
            "Assignee": ticket.assignee.full_name if ticket.assignee else "Unassigned",
            "Created At": (
                ticket.created_at.strftime("%Y-%m-%d %H:%M") if ticket.created_at else ""
            ),
            "Resolved At": (
                ticket.resolved_at.strftime("%Y-%m-%d %H:%M") if ticket.resolved_at else ""
            ),
            "SLA Breached": "Yes" if ticket.sla_breached else "No",
        }

    # =====================================================
    # Renderers — pure functions of (rows) -> bytes
    # =====================================================

    def to_csv_bytes(self, rows: list[dict]) -> bytes:
        """
        Render rows as CSV bytes.

        utf-8-sig (adds a BOM) so Excel opens the file with the correct
        encoding instead of mangling any non-ASCII characters — a classic
        gotcha when a plain utf-8 CSV is double-clicked open on Windows.
        """
        df = pd.DataFrame(rows, columns=REPORT_COLUMNS)
        return df.to_csv(index=False).encode("utf-8-sig")

    def to_excel_bytes(self, rows: list[dict]) -> bytes:
        """Render rows as an .xlsx workbook, returned as raw bytes."""
        df = pd.DataFrame(rows, columns=REPORT_COLUMNS)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Tickets")
        return buffer.getvalue()

    def to_pdf_bytes(self, rows: list[dict], title: str = "Ticket Report") -> bytes:
        """
        Render rows as a simple tabular PDF using reportlab.

        Landscape A4 — a 10-column ticket report is wide; portrait would
        force text small enough to be unreadable.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
        styles = getSampleStyleSheet()

        elements = [
            Paragraph(title, styles["Title"]),
            Paragraph(
                f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} "
                f"— {len(rows)} ticket(s)",
                styles["Normal"],
            ),
            Spacer(1, 12),
        ]

        table_data = [REPORT_COLUMNS] + [[row[col] for col in REPORT_COLUMNS] for row in rows]
        table = Table(table_data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f2f2f2")],
                    ),
                ]
            )
        )
        elements.append(table)
        doc.build(elements)
        return buffer.getvalue()
