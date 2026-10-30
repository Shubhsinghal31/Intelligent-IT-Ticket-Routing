"""
User management business logic.

Scope for this step: listing users (with role/department/status filters),
admin-side account creation (create_user), and activating/deactivating
accounts. Self-registration and password management live in AuthService
— create_user() here is deliberately separate from AuthService.register()
even though both end up inserting a User row, because they answer
different questions: register() answers "can anyone sign themselves up"
(yes, always as 'employee'), while create_user() answers "can an admin
provision an account with any role" (yes, admin-only, RBAC-gated at the
route layer). Collapsing them into one method would mean threading a
"who's calling and are they allowed to pick a role" check through a
single function used by both a public and a privileged endpoint — two
small, clearly-scoped methods are easier to reason about than one with a
security-critical branch inside it.

RBAC for these endpoints is enforced at the route layer via `require_roles`
(same pattern as backend/api/v1/endpoints/dashboard.py), not inside this
service. That's a deliberate distinction from TicketService: ticket RBAC
depends on *which* ticket (e.g. "your own"), so it has to live in the
service where the ticket is loaded. User listing/activation is a blanket
role gate with no per-resource ownership check, so the dependency alone
is sufficient — duplicating it here would just be dead code.
"""

import math

from loguru import logger
from sqlalchemy.orm import Session

from backend.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from backend.core.security import hash_password
from backend.models.department import Department
from backend.models.user import User
from backend.repositories.user_repository import UserRepository
from backend.schemas.user import UserCreate


class UserService:
    """Encapsulates user management workflows."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_repo = UserRepository(db)

    def _get_user_or_404(self, user_id: int) -> User:
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundException(f"User {user_id} not found")
        return user

    # =====================================================
    # List — paginated, filterable
    # =====================================================

    def get_users(
        self,
        page: int = 1,
        page_size: int = 20,
        role: str | None = None,
        department_id: int | None = None,
        is_active: bool | None = None,
    ) -> dict:
        """
        Return a paginated list of users.

        Used for two purposes:
        - Admin dashboard: manage the full roster
        - Ticket assignment picker: engineers/admins fetch role="engineer"
          to populate the "assign to" dropdown
        """
        users = self.user_repo.get_paginated(
            page=page,
            page_size=page_size,
            role_name=role,
            department_id=department_id,
            is_active=is_active,
        )
        total = self.user_repo.count(
            role_name=role,
            department_id=department_id,
            is_active=is_active,
        )

        return {
            "items": users,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total > 0 else 1,
        }

    # =====================================================
    # Create — admin provisions an account with any role
    # =====================================================

    def create_user(self, data: UserCreate) -> User:
        """
        Create a user with an admin-chosen role and (optional) department.

        This is the only way to create an engineer or admin account —
        self-registration (AuthService.register()) always hardcodes
        'employee'. Mirrors register()'s uniqueness/role-lookup checks
        rather than calling it, since register() has no way to accept a
        role and shouldn't be given one (see this module's docstring).
        """
        email = data.email.lower()
        username = data.username.lower()

        if self.user_repo.email_exists(email):
            raise ConflictException(f"Email '{email}' is already registered")
        if self.user_repo.username_exists(username):
            raise ConflictException(f"Username '{username}' is already taken")

        role = self.user_repo.get_role_by_name(data.role)
        if not role:
            raise NotFoundException(
                f"Role '{data.role}' does not exist. Expected one of: " "employee, engineer, admin."
            )

        if data.department_id is not None:
            department = self.db.get(Department, data.department_id)
            if not department:
                raise NotFoundException(f"Department {data.department_id} not found")

        user = User(
            email=email,
            username=username,
            password_hash=hash_password(data.password),
            full_name=data.full_name,
            role_id=role.id,
            department_id=data.department_id,
            is_active=True,
        )
        self.user_repo.add(user)
        self.user_repo.commit()
        self.db.refresh(user)

        logger.info(f"User created by admin: id={user.id} email={user.email} role={role.name}")
        return user

    # =====================================================
    # Deactivate — soft-disable an account
    # =====================================================

    def deactivate_user(self, user_id: int, acting_user: User) -> User:
        """
        Disable a user account. Deactivated users can no longer log in
        (see AuthService.authenticate — checks is_active).

        Guards against an admin locking themselves out, which would leave
        the system with no way to reactivate anyone.
        """
        if user_id == acting_user.id:
            raise ForbiddenException("You cannot deactivate your own account")

        user = self._get_user_or_404(user_id)
        user.is_active = False
        self.user_repo.commit()
        self.db.refresh(user)

        logger.info(f"User deactivated: id={user.id} by admin_id={acting_user.id}")
        return user

    # =====================================================
    # Activate — re-enable a disabled account
    # =====================================================

    def activate_user(self, user_id: int, acting_user: User) -> User:
        """Re-enable a previously deactivated account."""
        user = self._get_user_or_404(user_id)
        user.is_active = True
        self.user_repo.commit()
        self.db.refresh(user)

        logger.info(f"User activated: id={user.id} by admin_id={acting_user.id}")
        return user
