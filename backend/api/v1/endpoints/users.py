"""
User management endpoints.

GET /users is deliberately open to both engineers and admins (not admin-only):
engineers need it to populate the "assign to" picker when routing a ticket.
Mutating actions (deactivate/activate) are admin-only.
"""

from fastapi import APIRouter, Depends, Query

from backend.api.deps import get_current_active_user, get_user_service, require_roles
from backend.schemas.common import PaginatedResponse
from backend.schemas.user import UserCreate, UserResponse
from backend.services.user_service import UserService

router = APIRouter()


# =====================================================
# POST /users — admin creates an account with any role
# =====================================================
@router.post(
    "",
    response_model=UserResponse,
    status_code=201,
    summary="Create a user account (admin)",
    description="Admin-only. Unlike POST /auth/register (always 'employee'), "
    "this can create engineer or admin accounts and assign a department.",
    dependencies=[Depends(require_roles("admin"))],
)
def create_user(
    payload: UserCreate,
    user_service: UserService = Depends(get_user_service),
):
    user = user_service.create_user(payload)
    return UserResponse.from_orm_user(user)


# =====================================================
# GET /users — paginated, filterable roster
# =====================================================
@router.get(
    "",
    response_model=PaginatedResponse[UserResponse],
    summary="List users",
    description="Returns a paginated list of users. "
    "Engineers and admins only — engineers use this to find an assignee, "
    "admins use it to manage the roster.",
    dependencies=[Depends(require_roles("engineer", "admin"))],
)
def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    role: str | None = Query(default=None, description="Filter by role name, e.g. 'engineer'"),
    department_id: int | None = Query(default=None, ge=1),
    is_active: bool | None = Query(default=None),
    user_service: UserService = Depends(get_user_service),
):
    result = user_service.get_users(
        page=page,
        page_size=page_size,
        role=role,
        department_id=department_id,
        is_active=is_active,
    )
    return PaginatedResponse[UserResponse](
        items=[UserResponse.from_orm_user(u) for u in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


# =====================================================
# POST /users/{user_id}/deactivate
# =====================================================
@router.post(
    "/{user_id}/deactivate",
    response_model=UserResponse,
    summary="Deactivate a user account",
    description="Disables login for this user. Admin only. "
    "An admin cannot deactivate their own account.",
    dependencies=[Depends(require_roles("admin"))],
)
def deactivate_user(
    user_id: int,
    current_user=Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service),
):
    user = user_service.deactivate_user(user_id, current_user)
    return UserResponse.from_orm_user(user)


# =====================================================
# POST /users/{user_id}/activate
# =====================================================
@router.post(
    "/{user_id}/activate",
    response_model=UserResponse,
    summary="Re-activate a disabled user account",
    description="Restores login access for a previously deactivated user. Admin only.",
    dependencies=[Depends(require_roles("admin"))],
)
def activate_user(
    user_id: int,
    current_user=Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service),
):
    user = user_service.activate_user(user_id, current_user)
    return UserResponse.from_orm_user(user)
