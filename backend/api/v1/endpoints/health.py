"""
Health check endpoint.

Used by:
- Docker HEALTHCHECK
- Render uptime monitoring
- CI/CD smoke tests
- DevOps incident response
"""

from datetime import datetime

from fastapi import APIRouter, status
from loguru import logger

from backend.core.config import settings
from backend.core.database import check_db_connection
from backend.schemas.common import HealthCheckResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="System health check",
    description="Returns app status, version, and database connectivity",
)
def health_check() -> HealthCheckResponse:
    """
    Health check endpoint.

    Returns 200 with status info even if DB is down — DB status is in the body.
    External monitoring decides what to alert on.
    """
    db_ok = check_db_connection()
    if not db_ok:
        logger.warning("Health check: database unreachable")

    return HealthCheckResponse(
        status="ok" if db_ok else "degraded",
        app_name=settings.APP_NAME,
        app_version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        database_connected=db_ok,
        timestamp=datetime.utcnow(),
    )
