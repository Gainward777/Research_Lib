from controllers.utils.services.library.item_service import ItemService
from models.commands import CreateItemCommand
from models.results import SaveResult


class IngestionService:
    def __init__(self, items: ItemService) -> None:
        self.items = items

    async def ingest(
        self, command: CreateItemCommand, *, idempotency_key: str | None = None
    ) -> SaveResult:
        return await self.items.create(command, idempotency_key=idempotency_key)
