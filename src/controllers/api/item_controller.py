from fastapi import APIRouter, Depends, Header

from controllers.api.auth import require_read, require_write
from controllers.api.dependencies import get_container
from controllers.api.requests import CreateItemRequest, RelationRequest
from controllers.utils.bootstrap.dependencies import ApplicationContainer
from models.commands import CreateItemCommand
from models.library_item import Relation
from views.api.item_view import render_item
from views.api.responses import ItemResponse, RelationResponse, SaveResponse

router = APIRouter(prefix="/v1/items", tags=["items"])


@router.post("", response_model=SaveResponse, dependencies=[Depends(require_write)])
async def create_item(
    request: CreateItemRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    container: ApplicationContainer = Depends(get_container),
) -> SaveResponse:
    result = await container.items.create(
        CreateItemCommand.model_validate(request.model_dump()), idempotency_key=idempotency_key
    )
    return SaveResponse.model_validate(result.model_dump())


@router.get("/{item_id:path}", response_model=ItemResponse, dependencies=[Depends(require_read)])
async def get_item(
    item_id: str, container: ApplicationContainer = Depends(get_container)
) -> ItemResponse:
    item, slug = await container.items.get(item_id)
    return render_item(item, slug)


@router.post(
    "/{item_id}/relations",
    response_model=RelationResponse,
    dependencies=[Depends(require_write)],
)
async def add_relation(
    item_id: str,
    request: RelationRequest,
    container: ApplicationContainer = Depends(get_container),
) -> RelationResponse:
    item, slug = await container.relations.add(
        item_id, Relation.model_validate(request.model_dump())
    )
    return RelationResponse(item_id=item.id, slug=slug, related_count=len(item.related))
