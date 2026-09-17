from controllers.utils.services.library.item_service import ItemService
from models.access import SectionRef
from models.commands import CreateItemCommand
from models.enums import LibraryItemType, SourceKind
from models.results import SaveResult


class PublicationService:
    def __init__(self, items: ItemService) -> None:
        self.items = items

    async def save(
        self,
        title: str,
        summary: str,
        url: str | None,
        authors: list[str],
        idempotency_key: str | None = None,
        *,
        section: SectionRef | None = None,
    ) -> SaveResult:
        content = f"Источник: {url}" if url else ""
        return await self.items.create(
            CreateItemCommand(
                section=section,
                type=LibraryItemType.PUBLICATION,
                title=title,
                content=content,
                summary=summary,
                authors=authors,
                source_kind=SourceKind.API,
                metadata={"url": url},
            ),
            idempotency_key=idempotency_key,
        )
