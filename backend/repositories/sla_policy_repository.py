"""
SLA policy data access layer.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.sla_policy import SlaPolicy
from backend.repositories.base import BaseRepository


class SlaPolicyRepository(BaseRepository[SlaPolicy]):
    """Repository for the SlaPolicy entity."""

    def __init__(self, db: Session) -> None:
        super().__init__(SlaPolicy, db)

    def get_all(self) -> list[SlaPolicy]:
        """
        Return every SLA policy, ordered by priority severity.

        There are only ever four rows (one per TicketPriority value),
        so no pagination is needed here — unlike tickets/users.
        """
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        stmt = select(SlaPolicy)
        policies = list(self.db.scalars(stmt).all())
        return sorted(policies, key=lambda p: order.get(p.priority, 99))

    def get_by_priority(self, priority: str) -> SlaPolicy | None:
        stmt = select(SlaPolicy).where(SlaPolicy.priority == priority)
        return self.db.scalars(stmt).first()
