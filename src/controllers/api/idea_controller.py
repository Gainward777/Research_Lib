from fastapi import APIRouter, Depends, Header

from controllers.api.auth import require_write
from controllers.api.dependencies import get_container
from controllers.api.requests import IdeaRequest
from controllers.utils.bootstrap.dependencies import ApplicationContainer
from views.api.responses import SaveResponse

router = APIRouter(prefix="/v1/ideas", tags=["ideas"], dependencies=[Depends(require_write)])


@router.post("", response_model=SaveResponse)
async def save_idea(
    request: IdeaRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    container: ApplicationContainer = Depends(get_container),
) -> SaveResponse:
    result = await container.ideas.save(
        request.title,
        request.content,
        request.tags,
        idempotency_key,
        section=request.section,
    )
    return SaveResponse.model_validate(result.model_dump())
