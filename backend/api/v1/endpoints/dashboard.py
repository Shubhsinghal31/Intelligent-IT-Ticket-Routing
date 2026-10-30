"""
Dashboard endpoints — aggregated metrics for admin and engineer views.

All endpoints require engineer or admin role.
Route handlers are thin — all SQL lives in DashboardService.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.deps import get_db, require_roles
from backend.services.dashboard_service import DashboardService

router = APIRouter()


def get_dashboard_service(db: Session = Depends(get_db)) -> DashboardService:
    return DashboardService(db)


# =====================================================
# GET /dashboard/summary
# =====================================================
@router.get(
    "/summary",
    summary="Ticket summary counts",
    description="Returns open, in-progress, resolved, and closed ticket counts "
    "plus average resolution time. Engineers and admins only.",
    dependencies=[Depends(require_roles("engineer", "admin"))],
)
def get_summary(
    service: DashboardService = Depends(get_dashboard_service),
):
    return service.get_summary()


# =====================================================
# GET /dashboard/trends
# =====================================================
@router.get(
    "/trends",
    summary="Monthly ticket volume trend",
    description="Ticket counts grouped by month for the last 6 months.",
    dependencies=[Depends(require_roles("engineer", "admin"))],
)
def get_trends(
    service: DashboardService = Depends(get_dashboard_service),
):
    return service.get_monthly_trends()


# =====================================================
# GET /dashboard/sla
# =====================================================
@router.get(
    "/sla",
    summary="SLA breach rates by department",
    description="Percentage of tickets that breached SLA per department.",
    dependencies=[Depends(require_roles("engineer", "admin"))],
)
def get_sla_stats(
    service: DashboardService = Depends(get_dashboard_service),
):
    return service.get_sla_stats()


# =====================================================
# GET /dashboard/heatmap
# =====================================================
@router.get(
    "/heatmap",
    summary="Ticket volume heatmap (day of week x hour)",
    description="Ticket counts grouped by day-of-week and hour-of-day, "
    "for staffing/coverage planning. Engineers and admins only.",
    dependencies=[Depends(require_roles("engineer", "admin"))],
)
def get_heatmap(
    service: DashboardService = Depends(get_dashboard_service),
):
    return service.get_heatmap_data()


# =====================================================
# GET /dashboard/engineers
# =====================================================
@router.get(
    "/engineers",
    summary="Engineer performance metrics",
    description="Tickets assigned and resolved per engineer.",
    dependencies=[Depends(require_roles("engineer", "admin"))],
)
def get_engineer_stats(
    service: DashboardService = Depends(get_dashboard_service),
):
    return service.get_engineer_stats()
