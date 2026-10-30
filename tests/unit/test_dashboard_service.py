"""
Unit tests for DashboardService.

DashboardService talks to the database with raw SQLAlchemy Core
`select()`/`func` constructs rather than a repository, so there's
nothing meaningful to mock at the "repository" layer here — instead
these tests mock db.execute(...).all()/.scalar() to return fake Row-like
objects (via SimpleNamespace, which supports the same attribute access
as a real SQLAlchemy Row) and verify the *shaping* logic: percentage
rounding, key names, and None-handling. What these tests deliberately
do NOT verify is whether the SQL itself (the GROUP BY, the JOIN, the
date_trunc) is correct against a real schema — that's what
tests/integration is for. A unit test that mocked the query result
can't catch a wrong JOIN condition; only a real database can.

Case in point: the double-percentage bug found during Milestone 8
(breach_rate was already a 0-100 percentage from the backend, but the
frontend multiplied by 100 again) was a bug in the *consumer* of this
data, not in DashboardService itself — but it's exactly the kind of
off-by-a-factor-of-100 mistake these shaping tests are here to prevent
from being reintroduced on the backend side.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.models.ticket import TicketStatus
from backend.services.dashboard_service import DashboardService

# =====================================================
# Helpers
# =====================================================


def make_service():
    db = MagicMock()
    return DashboardService(db), db


# =====================================================
# get_summary()
# =====================================================


class TestGetSummary:
    def test_counts_by_status_and_average_resolution(self):
        service, db = make_service()

        status_rows = [
            SimpleNamespace(status=TicketStatus.OPEN, count=5),
            SimpleNamespace(status=TicketStatus.RESOLVED, count=3),
            SimpleNamespace(status=TicketStatus.CLOSED, count=2),
        ]
        status_result = MagicMock()
        status_result.all.return_value = status_rows

        avg_result = MagicMock()
        avg_result.scalar.return_value = 12.345

        db.execute.side_effect = [status_result, avg_result]

        summary = service.get_summary()

        assert summary["open"] == 5
        assert summary["resolved"] == 3
        assert summary["closed"] == 2
        assert summary["in_progress"] == 0  # not present in status_rows
        assert summary["total"] == 10
        assert summary["avg_resolution_hours"] == 12.35  # rounded to 2 places

    def test_no_resolved_tickets_yields_none_average(self):
        service, db = make_service()

        status_result = MagicMock()
        status_result.all.return_value = []
        avg_result = MagicMock()
        avg_result.scalar.return_value = None

        db.execute.side_effect = [status_result, avg_result]

        summary = service.get_summary()

        assert summary["total"] == 0
        assert summary["avg_resolution_hours"] is None


# =====================================================
# get_monthly_trends()
# =====================================================


class TestGetMonthlyTrends:
    """
    get_monthly_trends() issues two separate queries (created_at-grouped,
    then resolved_at-grouped) and merges them in Python — so these tests
    configure db.execute's side_effect with two results in that order,
    matching the two real self.db.execute(...) calls in the service.
    """

    def test_formats_month_as_year_dash_month_when_created_equals_resolved(self):
        service, db = make_service()

        created_result = MagicMock()
        created_result.all.return_value = [
            SimpleNamespace(month=datetime(2026, 1, 1), count=8),
            SimpleNamespace(month=datetime(2026, 2, 1), count=15),
        ]
        resolved_result = MagicMock()
        resolved_result.all.return_value = [
            SimpleNamespace(month=datetime(2026, 1, 1), count=5),
            SimpleNamespace(month=datetime(2026, 2, 1), count=10),
        ]
        db.execute.side_effect = [created_result, resolved_result]

        trends = service.get_monthly_trends()

        assert trends == [
            {"month": "2026-01", "created": 8, "resolved": 5},
            {"month": "2026-02", "created": 15, "resolved": 10},
        ]

    def test_month_with_only_created_tickets_defaults_resolved_to_zero(self):
        """
        A ticket created this month but not yet resolved should still
        appear in the chart with resolved=0, not be dropped — this is
        exactly the scenario a fresh database with one open ticket hits.
        """
        service, db = make_service()

        created_result = MagicMock()
        created_result.all.return_value = [
            SimpleNamespace(month=datetime(2026, 7, 1), count=1),
        ]
        resolved_result = MagicMock()
        resolved_result.all.return_value = []
        db.execute.side_effect = [created_result, resolved_result]

        trends = service.get_monthly_trends()

        assert trends == [{"month": "2026-07", "created": 1, "resolved": 0}]

    def test_ticket_created_and_resolved_in_different_months_both_counted(self):
        """
        A ticket created in June but resolved in July should contribute
        to June's "created" count and July's "resolved" count as two
        separate rows, not be merged into one.
        """
        service, db = make_service()

        created_result = MagicMock()
        created_result.all.return_value = [
            SimpleNamespace(month=datetime(2026, 6, 1), count=1),
        ]
        resolved_result = MagicMock()
        resolved_result.all.return_value = [
            SimpleNamespace(month=datetime(2026, 7, 1), count=1),
        ]
        db.execute.side_effect = [created_result, resolved_result]

        trends = service.get_monthly_trends()

        assert trends == [
            {"month": "2026-06", "created": 1, "resolved": 0},
            {"month": "2026-07", "created": 0, "resolved": 1},
        ]


# =====================================================
# get_sla_stats()
# =====================================================


class TestGetSlaStats:
    def test_computes_breach_rate_as_percentage(self):
        service, db = make_service()

        rows = [
            SimpleNamespace(department="IT Support", total=10, breached=5),
            SimpleNamespace(department="Network", total=4, breached=0),
        ]
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        db.execute.return_value = result_mock

        stats = service.get_sla_stats()

        assert stats[0] == {
            "department": "IT Support",
            "total_tickets": 10,
            "breached": 5,
            "breach_rate": 50.0,
        }
        assert stats[1]["breach_rate"] == 0.0

    def test_zero_tickets_does_not_divide_by_zero(self):
        service, db = make_service()

        rows = [SimpleNamespace(department="Empty Dept", total=0, breached=0)]
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        db.execute.return_value = result_mock

        stats = service.get_sla_stats()

        assert stats[0]["breach_rate"] == 0


# =====================================================
# get_heatmap_data()
# =====================================================


class TestGetHeatmapData:
    def test_casts_extracted_values_to_int(self):
        """
        Postgres EXTRACT() returns a float/Decimal, not an int — the
        service casts explicitly. Using float inputs here (1.0, 14.0)
        mirrors what the real driver would hand back.
        """
        service, db = make_service()

        rows = [SimpleNamespace(day_of_week=1.0, hour=14.0, count=3)]
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        db.execute.return_value = result_mock

        heatmap = service.get_heatmap_data()

        assert heatmap == [{"day_of_week": 1, "hour": 14, "count": 3}]
        assert isinstance(heatmap[0]["day_of_week"], int)
        assert isinstance(heatmap[0]["hour"], int)


# =====================================================
# get_engineer_stats()
# =====================================================


class TestGetEngineerStats:
    def test_computes_resolution_rate_as_percentage(self):
        service, db = make_service()

        rows = [SimpleNamespace(engineer="Bob", assigned=10, resolved=7)]
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        db.execute.return_value = result_mock

        stats = service.get_engineer_stats()

        assert stats[0] == {
            "engineer": "Bob",
            "tickets_assigned": 10,
            "tickets_resolved": 7,
            "resolution_rate": 70.0,
        }

    def test_zero_assigned_does_not_divide_by_zero(self):
        service, db = make_service()

        rows = [SimpleNamespace(engineer="Idle Bob", assigned=0, resolved=0)]
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        db.execute.return_value = result_mock

        stats = service.get_engineer_stats()

        assert stats[0]["resolution_rate"] == 0
