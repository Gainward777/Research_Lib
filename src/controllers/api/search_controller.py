from fastapi import APIRouter, Depends

from controllers.api.auth import require_read
from controllers.api.dependencies import get_container
from controllers.api.requests import SearchRequest
from controllers.utils.bootstrap.dependencies import ApplicationContainer
from models.commands import SearchCommand
from views.api.responses import AnswerResponse, SearchResponse

router = APIRouter(prefix="/v1", tags=["search"], dependencies=[Depends(require_read)])


@router.post("/search", response_model=SearchResponse)
async def search(
    request: SearchRequest, container: ApplicationContainer = Depends(get_container)
) -> SearchResponse:
    command = SearchCommand.model_validate(request.model_dump())
    return SearchResponse(hits=await container.search.search(command))


@router.post("/ask", response_model=AnswerResponse)
async def ask(
    request: SearchRequest, container: ApplicationContainer = Depends(get_container)
) -> AnswerResponse:
    command = SearchCommand.model_validate({**request.model_dump(), "synthesize": True})
    return AnswerResponse.model_validate(await container.search.ask(command))
