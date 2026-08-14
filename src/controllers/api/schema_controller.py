from fastapi import APIRouter, Depends

from controllers.api.auth import require_read, require_write
from controllers.api.dependencies import get_container
from controllers.api.requests import SchemaProposalRequest
from controllers.utils.bootstrap.dependencies import ApplicationContainer
from views.api.responses import ProposalResponse

router = APIRouter(prefix="/v1/schema/proposals", tags=["schema"])


@router.post("", response_model=ProposalResponse, dependencies=[Depends(require_write)])
async def create_proposal(
    request: SchemaProposalRequest,
    container: ApplicationContainer = Depends(get_container),
) -> ProposalResponse:
    result = await container.proposals.create(request.kind, request.name, request.payload)
    return ProposalResponse.model_validate(result)


@router.get("", response_model=list[ProposalResponse], dependencies=[Depends(require_read)])
async def list_proposals(
    container: ApplicationContainer = Depends(get_container),
) -> list[ProposalResponse]:
    return [ProposalResponse.model_validate(item) for item in await container.proposals.list()]


@router.post(
    "/{proposal_id}/apply",
    response_model=ProposalResponse,
    dependencies=[Depends(require_write)],
)
async def apply_proposal(
    proposal_id: str, container: ApplicationContainer = Depends(get_container)
) -> ProposalResponse:
    return ProposalResponse.model_validate(await container.proposals.apply(proposal_id))
