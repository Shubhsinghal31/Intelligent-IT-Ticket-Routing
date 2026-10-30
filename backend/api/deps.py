"""
Reusable FastAPI dependencies.

Centralizes: DB session, current user, role-checking.
"""

from collections.abc import Callable

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.exceptions import ForbiddenException
from backend.models.user import User
from backend.services.attachment_service import AttachmentService
from backend.services.auth_service import AuthService
from backend.services.comment_service import CommentService
from backend.services.department_service import DepartmentService
from backend.services.report_service import ReportService
from backend.services.sla_policy_service import SlaPolicyService
from backend.services.ticket_service import TicketService
from backend.services.user_service import UserService

# OAuth2 scheme: extracts "Bearer <token>" from Authorization header
# tokenUrl is where Swagger UI's "Authorize" button POSTs credentials
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login",
    auto_error=True,
)


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    """Inject an AuthService bound to the request's DB session."""
    return AuthService(db)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """
    Authentication dependency.

    Usage:
        @router.get("/me")
        def read_me(user: User = Depends(get_current_user)):
            ...
    """
    return auth_service.get_user_from_token(token)


def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    """Same as get_current_user but enforces is_active (defense in depth)."""
    if not user.is_active:
        raise ForbiddenException("Account is disabled")
    return user


def require_roles(*allowed_roles: str) -> Callable[[User], User]:
    """
    Authorization dependency factory.

    Returns a dependency that allows only users with one of `allowed_roles`.

    Usage:
        @router.delete("/users/{id}", dependencies=[Depends(require_roles("admin"))])
        def delete_user(...): ...

    Or:
        def endpoint(user: User = Depends(require_roles("admin", "engineer"))):
            ...
    """

    def _role_checker(user: User = Depends(get_current_active_user)) -> User:
        if user.role.name not in allowed_roles:
            raise ForbiddenException(
                f"This action requires one of roles: {', '.join(allowed_roles)}"
            )
        return user

    return _role_checker


def get_ticket_service(db: Session = Depends(get_db)) -> TicketService:
    """Inject a TicketService bound to the request's DB session."""
    return TicketService(db)


def get_comment_service(db: Session = Depends(get_db)) -> CommentService:
    """Inject a CommentService bound to the request's DB session."""
    return CommentService(db)


def get_attachment_service(db: Session = Depends(get_db)) -> AttachmentService:
    """Inject an AttachmentService bound to the request's DB session."""
    return AttachmentService(db)


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """Inject a UserService bound to the request's DB session."""
    return UserService(db)


def get_sla_policy_service(db: Session = Depends(get_db)) -> SlaPolicyService:
    """Inject an SlaPolicyService bound to the request's DB session."""
    return SlaPolicyService(db)


def get_report_service(db: Session = Depends(get_db)) -> ReportService:
    """Inject a ReportService bound to the request's DB session."""
    return ReportService(db)


def get_department_service(db: Session = Depends(get_db)) -> DepartmentService:
    """Inject a DepartmentService bound to the request's DB session."""
    return DepartmentService(db)
