from fastapi import APIRouter, Depends

from controllers.api.auth import require_read, require_write
from controllers.api.dependencies import get_container
from controllers.api.requests import SchemaProposalRequest
from controllers.utils.bootstrap.dependencies import ApplicationContainer
from models.access import AuthorizationContext
from views.api.responses import ProposalResponse

router = APIRouter(prefix="/v1/schema/proposals", tags=["schema"])


@router.post("", response_model=ProposalResponse)
async def create_proposal(
    request: SchemaProposalRequest,
    auth: AuthorizationContext = Depends(require_write),
    container: ApplicationContainer = Depends(get_container),
) -> ProposalResponse:
    await container.authorization.require_admin(auth)
    result = await container.proposals.create(request.kind, request.name, request.payload)
    return ProposalResponse.model_validate(result)


@router.get("", response_model=list[ProposalResponse])
async def list_proposals(
    auth: AuthorizationContext = Depends(require_read),
    container: ApplicationContainer = Depends(get_container),
) -> list[ProposalResponse]:
    await container.authorization.require_admin(auth)
    return [ProposalResponse.model_validate(item) for item in await container.proposals.list()]


@router.post("/{proposal_id}/apply", response_model=ProposalResponse)
async def apply_proposal(
    proposal_id: str,
    auth: AuthorizationContext = Depends(require_write),
    container: ApplicationContainer = Depends(get_container),
) -> ProposalResponse:
    await container.authorization.require_admin(auth)
    return ProposalResponse.model_validate(await container.proposals.apply(proposal_id))
