"""
Aggregates all v1 endpoint routers into a single router.
"""

from fastapi import APIRouter

from backend.api.v1.endpoints import (
    auth,
    dashboard,
    departments,
    health,
    reports,
    sla_policies,
    tickets,
    users,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(tickets.router, prefix="/tickets", tags=["Tickets"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(departments.router, prefix="/departments", tags=["Departments"])
api_router.include_router(sla_policies.router, prefix="/sla-policies", tags=["SLA Policies"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])

api_router.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["Dashboard"],
)
