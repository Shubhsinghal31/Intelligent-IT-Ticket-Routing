"""
Department endpoints.

Read-only today — see DepartmentService's docstring. Gated to
engineer/admin (same as GET /users) since the only current consumer is
the admin "Add User" form's department picker; employees have no UI
that needs a department list.
"""

from fastapi import APIRouter, Depends

from backend.api.deps import get_department_service, require_roles
from backend.schemas.department import DepartmentResponse
from backend.services.department_service import DepartmentService

router = APIRouter()


@router.get(
    "",
    response_model=list[DepartmentResponse],
    summary="List active departments",
    description="Returns all active departments, alphabetical. Engineers and admins only.",
    dependencies=[Depends(require_roles("engineer", "admin"))],
)
def list_departments(
    department_service: DepartmentService = Depends(get_department_service),
):
    return department_service.list_departments()
