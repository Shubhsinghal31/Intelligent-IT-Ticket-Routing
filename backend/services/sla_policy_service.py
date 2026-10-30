"""
SLA policy business logic.

Scope: view all policies, and let an admin adjust the response/resolution
hour thresholds. Policies aren't created or deleted through the API — the
four priority levels are fixed by the TicketPriority enum (see migration
005_create_sla_policies_table.sql and seed 003_seed_sla_policies.sql), so
"management" here means tuning the numbers, not managing the row set.
"""

from loguru import logger
from sqlalchemy.orm import Session

from backend.core.exceptions import NotFoundException
from backend.models.sla_policy import SlaPolicy
from backend.repositories.sla_policy_repository import SlaPolicyRepository
from backend.schemas.sla_policy import SlaPolicyUpdate


class SlaPolicyService:
    """Encapsulates SLA policy workflows."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = SlaPolicyRepository(db)

    def list_policies(self) -> list[SlaPolicy]:
        return self.repo.get_all()

    def update_policy(self, policy_id: int, data: SlaPolicyUpdate) -> SlaPolicy:
        """
        Apply a partial update to an SLA policy's thresholds.

        Note: this only affects tickets created AFTER the change.
        sla_due_at is computed once, at ticket-creation time
        (see TicketService.create_ticket), and is not retroactively
        recalculated for existing tickets when a policy changes.
        """
        policy = self.repo.get_by_id(policy_id)
        if not policy:
            raise NotFoundException(f"SLA policy {policy_id} not found")

        if data.response_time_hours is not None:
            policy.response_time_hours = data.response_time_hours
        if data.resolution_time_hours is not None:
            policy.resolution_time_hours = data.resolution_time_hours
        if data.description is not None:
            policy.description = data.description

        self.repo.commit()
        self.db.refresh(policy)

        logger.info(f"SLA policy updated: id={policy.id} priority={policy.priority}")
        return policy
