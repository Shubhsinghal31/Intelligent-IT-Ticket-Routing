"""
SLA policy endpoints.

GET is engineer+admin (both benefit from seeing current thresholds).
PATCH is admin-only — changing SLA commitments is a policy decision.
"""

from fastapi import APIRouter, Depends

from backend.api.deps import get_sla_policy_service, require_roles
from backend.schemas.sla_policy import SlaPolicyResponse, SlaPolicyUpdate
from backend.services.sla_policy_service import SlaPolicyService

router = APIRouter()


@router.get(
    "",
    response_model=list[SlaPolicyResponse],
    summary="List SLA policies",
    description="Returns all four SLA policies (one per priority level). "
    "Engineers and admins only.",
    dependencies=[Depends(require_roles("engineer", "admin"))],
)
def list_sla_policies(
    service: SlaPolicyService = Depends(get_sla_policy_service),
):
    return service.list_policies()


@router.patch(
    "/{policy_id}",
    response_model=SlaPolicyResponse,
    summary="Update an SLA policy's thresholds",
    description="Adjusts response/resolution hour targets for a priority level. "
    "Only affects tickets created after the change. Admin only.",
    dependencies=[Depends(require_roles("admin"))],
)
def update_sla_policy(
    policy_id: int,
    payload: SlaPolicyUpdate,
    service: SlaPolicyService = Depends(get_sla_policy_service),
):
    return service.update_policy(policy_id, payload)
