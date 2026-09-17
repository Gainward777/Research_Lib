from fastapi import APIRouter, Depends, Header

from controllers.api.auth import require_write
from controllers.api.dependencies import get_container
from controllers.api.requests import PublicationRequest
from controllers.utils.bootstrap.dependencies import ApplicationContainer
from views.api.responses import SaveResponse

router = APIRouter(
    prefix="/v1/publications", tags=["publications"], dependencies=[Depends(require_write)]
)


@router.post("", response_model=SaveResponse)
async def save_publication(
    request: PublicationRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    container: ApplicationContainer = Depends(get_container),
) -> SaveResponse:
    result = await container.publications.save(
        request.title,
        request.summary,
        str(request.url) if request.url else None,
        request.authors,
        idempotency_key,
        section=request.section,
    )
    return SaveResponse.model_validate(result.model_dump())
