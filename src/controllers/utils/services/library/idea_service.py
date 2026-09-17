from controllers.utils.services.library.item_service import ItemService
from models.access import SectionRef
from models.commands import CreateItemCommand
from models.enums import LibraryItemType, SourceKind
from models.results import SaveResult


class IdeaService:
    def __init__(self, items: ItemService) -> None:
        self.items = items

    async def save(
        self,
        title: str,
        content: str,
        tags: list[str],
        idempotency_key: str | None = None,
        *,
        section: SectionRef | None = None,
    ) -> SaveResult:
        return await self.items.create(
            CreateItemCommand(
                section=section,
                type=LibraryItemType.IDEA,
                title=title,
                content=content,
                tags=tags,
                source_kind=SourceKind.API,
            ),
            idempotency_key=idempotency_key,
        )
