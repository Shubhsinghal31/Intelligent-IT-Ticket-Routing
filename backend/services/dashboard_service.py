"""
Dashboard business logic — aggregation queries.

All queries use SQLAlchemy Core (select + func) rather than ORM
for performance. Aggregation queries don't need ORM object hydration.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from backend.models.department import Department
from backend.models.ticket import Ticket, TicketStatus
from backend.models.user import User


class DashboardService:

    def __init__(self, db: Session) -> None:
        self.db = db

    # =====================================================
    # Summary counts
    # =====================================================

    def get_summary(self) -> dict:
        """
        Returns total counts per status and average resolution time.
        """
        # Count tickets grouped by status
        status_counts = self.db.execute(
            select(Ticket.status, func.count(Ticket.id).label("count")).group_by(Ticket.status)
        ).all()

        counts = {row.status.value: row.count for row in status_counts}

        # Average resolution time in hours (only resolved/closed tickets)
        avg_result = self.db.execute(
            select(
                func.avg(
                    func.extract("epoch", Ticket.resolved_at - Ticket.created_at) / 3600
                ).label("avg_hours")
            ).where(Ticket.resolved_at.isnot(None))
        ).scalar()

        return {
            "open": counts.get("open", 0),
            "in_progress": counts.get("in_progress", 0),
            "resolved": counts.get("resolved", 0),
            "closed": counts.get("closed", 0),
            "reopened": counts.get("reopened", 0),
            "total": sum(counts.values()),
            "avg_resolution_hours": round(float(avg_result), 2) if avg_result else None,
        }

    # =====================================================
    # Monthly trends
    # =====================================================

    def get_monthly_trends(self) -> list[dict]:
        """
        Ticket counts grouped by month for the last 6 months, split into
        tickets created vs. tickets resolved that month.

        These are two independent monthly counts, not a running total —
        a ticket created in June but resolved in July contributes to
        June's "created" count and July's "resolved" count separately.
        Computed as two separate aggregate queries (one grouped by
        created_at, one by resolved_at) rather than a single query with
        one GROUP BY, since a single ticket's creation month and
        resolution month can differ — one query can only group by one
        of those two columns at a time. The two result sets are merged
        in Python: cheap, since this is at most a handful of months of
        data, and it avoids a FULL OUTER JOIN just to align two
        differently-grouped aggregates. Months with activity in only one
        series default the other to 0 rather than being omitted, so the
        frontend's two-line chart doesn't show a gap.
        """
        six_months_ago = datetime.now(timezone.utc) - timedelta(days=180)

        created_rows = self.db.execute(
            select(
                func.date_trunc("month", Ticket.created_at).label("month"),
                func.count(Ticket.id).label("count"),
            )
            .where(Ticket.created_at >= six_months_ago)
            .group_by("month")
        ).all()

        resolved_rows = self.db.execute(
            select(
                func.date_trunc("month", Ticket.resolved_at).label("month"),
                func.count(Ticket.id).label("count"),
            )
            .where(Ticket.resolved_at.isnot(None), Ticket.resolved_at >= six_months_ago)
            .group_by("month")
        ).all()

        by_month: dict[str, dict[str, int]] = {}
        for row in created_rows:
            key = row.month.strftime("%Y-%m")
            by_month.setdefault(key, {"created": 0, "resolved": 0})["created"] = row.count
        for row in resolved_rows:
            key = row.month.strftime("%Y-%m")
            by_month.setdefault(key, {"created": 0, "resolved": 0})["resolved"] = row.count

        return [
            {"month": month, "created": counts["created"], "resolved": counts["resolved"]}
            for month, counts in sorted(by_month.items())
        ]

    # =====================================================
    # SLA stats by department
    # =====================================================

    def get_sla_stats(self) -> list[dict]:
        """
        SLA breach rate per department.

        "Breached" counts two cases:
        1. Ticket.sla_breached is True — set by TicketService.resolve_ticket()
           when a ticket was resolved after its due date.
        2. The ticket is still open/in-progress and its due date has already
           passed — a real breach even though nothing has resolved it yet.
        Without case 2, a department with many overdue-but-unresolved
        tickets would misleadingly show 0% breach rate until someone
        finally resolves them.
        """
        currently_overdue = and_(
            Ticket.resolved_at.is_(None),
            Ticket.sla_due_at.isnot(None),
            Ticket.sla_due_at < func.now(),
            Ticket.status != TicketStatus.CLOSED,
        )
        is_breached = case(
            (Ticket.sla_breached, 1),
            (currently_overdue, 1),
            else_=0,
        )

        rows = self.db.execute(
            select(
                Department.name.label("department"),
                func.count(Ticket.id).label("total"),
                func.sum(is_breached).label("breached"),
            )
            .join(Department, Ticket.department_id == Department.id)
            .group_by(Department.name)
            .order_by(Department.name)
        ).all()

        return [
            {
                "department": row.department,
                "total_tickets": row.total,
                "breached": int(row.breached),
                "breach_rate": round(row.breached / row.total * 100, 1) if row.total else 0,
            }
            for row in rows
        ]

    # =====================================================
    # Ticket volume heatmap — day of week x hour of day
    # =====================================================

    def get_heatmap_data(self) -> list[dict]:
        """
        Ticket counts grouped by day-of-week and hour-of-day.

        Answers "when do tickets actually come in?" — a staffing question
        the monthly trend chart can't answer (that's volume over months,
        this is volume within a week). Postgres EXTRACT(DOW ...) returns
        0=Sunday through 6=Saturday; the frontend maps that to labels.

        Only day/hour combinations that have at least one ticket are
        returned — the frontend fills in the zero cells when it builds
        the 7x24 grid, so a sparse result set here is expected and fine.
        """
        rows = self.db.execute(
            select(
                func.extract("dow", Ticket.created_at).label("day_of_week"),
                func.extract("hour", Ticket.created_at).label("hour"),
                func.count(Ticket.id).label("count"),
            ).group_by("day_of_week", "hour")
        ).all()

        return [
            {
                "day_of_week": int(row.day_of_week),
                "hour": int(row.hour),
                "count": row.count,
            }
            for row in rows
        ]

    # =====================================================
    # Engineer performance
    # =====================================================

    def get_engineer_stats(self) -> list[dict]:
        """
        Tickets assigned and resolved per engineer.
        """
        rows = self.db.execute(
            select(
                User.full_name.label("engineer"),
                func.count(Ticket.id).label("assigned"),
                func.sum(
                    case((Ticket.status == TicketStatus.RESOLVED, 1), else_=0)
                    + case((Ticket.status == TicketStatus.CLOSED, 1), else_=0)
                ).label("resolved"),
            )
            .join(User, Ticket.assigned_to_id == User.id)
            .group_by(User.full_name)
            .order_by(func.count(Ticket.id).desc())
        ).all()

        return [
            {
                "engineer": row.engineer,
                "tickets_assigned": row.assigned,
                "tickets_resolved": int(row.resolved),
                "resolution_rate": (
                    round(row.resolved / row.assigned * 100, 1) if row.assigned else 0
                ),
            }
            for row in rows
        ]
