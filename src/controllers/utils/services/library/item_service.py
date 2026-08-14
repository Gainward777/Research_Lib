from datetime import UTC, datetime

from controllers.utils.BD.attachments import AttachmentStore
from controllers.utils.BD.jobs import JobStore
from controllers.utils.BD.markdown import MarkdownItemRepository
from controllers.utils.BD.receipts import ReceiptStore, payload_hash
from controllers.utils.infrastructure.gbrain.adapter import GBrainAdapter
from errors import NotFoundError
from models.commands import CreateItemCommand
from models.library_item import LibraryItem, Relation
from models.results import SaveResult


class ItemService:
    def __init__(
        self,
        repository: MarkdownItemRepository,
        attachments: AttachmentStore,
        receipts: ReceiptStore,
        jobs: JobStore,
        gbrain: GBrainAdapter,
    ) -> None:
        self.repository = repository
        self.attachments = attachments
        self.receipts = receipts
        self.jobs = jobs
        self.gbrain = gbrain

    async def create(
        self, command: CreateItemCommand, *, idempotency_key: str | None = None
    ) -> SaveResult:
        payload = command.model_dump(mode="json")
        digest = payload_hash(payload)
        if idempotency_key:
            previous = await self.receipts.get(idempotency_key, digest)
            if previous is not None:
                return SaveResult.model_validate(previous)

        item = LibraryItem(
            type=command.type,
            title=command.title,
            content=command.content,
            summary=command.summary,
            source_kind=command.source_kind,
            source_external_id=command.source_external_id,
            authors=command.authors,
            tags=command.tags,
            metadata=command.metadata,
        )
        for upload_id in command.attachment_upload_ids:
            item.attachments.append(await self.attachments.consume(upload_id, item.id))

        slug = await self.repository.save(item)
        indexed = True
        warnings: list[str] = []
        try:
            await self.gbrain.index(item)
            await self.repository.mark_indexed(item.id)
        except Exception as exc:  # durable Markdown must survive index failures
            indexed = False
            warnings.append("Материал сохранён, но ожидает повторной индексации")
            await self.jobs.create_pending_index(item.id, str(exc))

        result = SaveResult(
            item_id=item.id, slug=slug, created=True, indexed=indexed, warnings=warnings
        )
        if idempotency_key:
            await self.receipts.save(idempotency_key, digest, result.model_dump(mode="json"))
        return result

    async def get(self, item_id_or_slug: str) -> tuple[LibraryItem, str]:
        result = await self.repository.get(item_id_or_slug)
        if result is None:
            raise NotFoundError(f"Library item not found: {item_id_or_slug}")
        return result

    async def add_relation(self, source_id: str, relation: Relation) -> tuple[LibraryItem, str]:
        item, slug = await self.get(source_id)
        await self.get(relation.target_id)
        if relation not in item.related:
            item.related.append(relation)
            item.updated_at = datetime.now(UTC)
            await self.repository.database.execute(
                "INSERT OR IGNORE INTO relations(source_id, relation_type, target_id) "
                "VALUES (?, ?, ?)",
                (source_id, relation.type.value, relation.target_id),
            )
            slug = await self.repository.save(item)
            await self.gbrain.index(item)
            await self.repository.mark_indexed(item.id)
        return item, slug
