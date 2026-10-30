"""
Unit tests for ReportService.

Data-fetch tests mock the repository (no DB needed). Renderer tests call
the real pandas/openpyxl/reportlab code against small in-memory row lists
and check the output is a well-formed file of the right type — full
parsing isn't necessary, just confirming each renderer produces a real,
non-empty file with the correct signature bytes.
"""

from datetime import datetime
from unittest.mock import MagicMock

from backend.models.ticket import TicketPriority, TicketStatus
from backend.services.report_service import REPORT_COLUMNS, ReportService


def make_service():
    db = MagicMock()
    service = ReportService(db)
    service.ticket_repo = MagicMock()
    return service


def make_mock_ticket(**overrides):
    """Build a MagicMock ticket with every field _flatten() reads set explicitly."""
    ticket = MagicMock()
    ticket.ticket_number = "TKT-2026-00001"
    ticket.title = "VPN not working"
    ticket.status = TicketStatus.OPEN
    ticket.priority = TicketPriority.HIGH
    ticket.department = MagicMock(name="dept")
    ticket.department.name = "Network"
    ticket.reporter = MagicMock(full_name="Alice Reporter")
    ticket.reporter.full_name = "Alice Reporter"
    ticket.assignee = None
    ticket.created_at = datetime(2026, 1, 15, 10, 30)
    ticket.resolved_at = None
    ticket.sla_breached = False
    for key, value in overrides.items():
        setattr(ticket, key, value)
    return ticket


class TestGetTicketRows:

    def test_flattens_ticket_into_expected_columns(self):
        service = make_service()
        service.ticket_repo.get_all_filtered.return_value = [make_mock_ticket()]

        rows = service.get_ticket_rows()

        assert len(rows) == 1
        row = rows[0]
        assert set(row.keys()) == set(REPORT_COLUMNS)
        assert row["Ticket Number"] == "TKT-2026-00001"
        assert row["Department"] == "Network"
        assert row["Assignee"] == "Unassigned"  # None -> "Unassigned"
        assert row["SLA Breached"] == "No"

    def test_breached_ticket_flag_is_yes(self):
        service = make_service()
        service.ticket_repo.get_all_filtered.return_value = [make_mock_ticket(sla_breached=True)]

        rows = service.get_ticket_rows()

        assert rows[0]["SLA Breached"] == "Yes"

    def test_forwards_filters_to_repository(self):
        service = make_service()
        service.ticket_repo.get_all_filtered.return_value = []

        service.get_ticket_rows(status=TicketStatus.OPEN, priority=TicketPriority.HIGH)

        service.ticket_repo.get_all_filtered.assert_called_once_with(
            status=TicketStatus.OPEN,
            priority=TicketPriority.HIGH,
            department_id=None,
            date_from=None,
            date_to=None,
        )

    def test_empty_result_returns_empty_list(self):
        service = make_service()
        service.ticket_repo.get_all_filtered.return_value = []

        assert service.get_ticket_rows() == []


class TestRenderers:
    """These exercise the real pandas/openpyxl/reportlab code paths."""

    SAMPLE_ROWS = [
        {
            "Ticket Number": "TKT-2026-00001",
            "Title": "VPN not working",
            "Status": "open",
            "Priority": "high",
            "Department": "Network",
            "Reporter": "Alice Reporter",
            "Assignee": "Unassigned",
            "Created At": "2026-01-15 10:30",
            "Resolved At": "",
            "SLA Breached": "No",
        }
    ]

    def test_csv_bytes_contains_header_and_row(self):
        service = make_service()

        content = service.to_csv_bytes(self.SAMPLE_ROWS)
        text = content.decode("utf-8-sig")

        assert "Ticket Number" in text
        assert "TKT-2026-00001" in text

    def test_csv_bytes_on_empty_rows_still_has_header(self):
        service = make_service()

        content = service.to_csv_bytes([])
        text = content.decode("utf-8-sig")

        assert "Ticket Number" in text

    def test_excel_bytes_has_valid_xlsx_signature(self):
        service = make_service()

        content = service.to_excel_bytes(self.SAMPLE_ROWS)

        # .xlsx is a zip archive — every zip file starts with "PK"
        assert content[:2] == b"PK"
        assert len(content) > 0

    def test_pdf_bytes_has_valid_pdf_signature(self):
        service = make_service()

        content = service.to_pdf_bytes(self.SAMPLE_ROWS)

        assert content[:5] == b"%PDF-"

    def test_pdf_bytes_on_empty_rows_does_not_crash(self):
        service = make_service()

        content = service.to_pdf_bytes([])

        assert content[:5] == b"%PDF-"
