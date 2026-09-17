from datetime import UTC, datetime

from controllers.utils.BD.attachments import AttachmentStore
from controllers.utils.BD.jobs import JobStore
from controllers.utils.BD.markdown import MarkdownItemRepository
from controllers.utils.BD.receipts import ReceiptStore, payload_hash
from controllers.utils.BD.sections import SectionStore
from controllers.utils.infrastructure.gbrain.adapter import GBrainAdapter
from controllers.utils.services.access.authorization_service import AuthorizationService
from controllers.utils.services.access.context import current_authorization
from errors import NotFoundError
from models.access import AuthorizationContext, SectionDomain
from models.commands import CreateItemCommand
from models.enums import LibraryItemType
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
        sections: SectionStore,
        authorization: AuthorizationService,
    ) -> None:
        self.repository = repository
        self.attachments = attachments
        self.receipts = receipts
        self.jobs = jobs
        self.gbrain = gbrain
        self.sections = sections
        self.authorization = authorization

    async def create(
        self,
        command: CreateItemCommand,
        *,
        idempotency_key: str | None = None,
        auth: AuthorizationContext | None = None,
    ) -> SaveResult:
        context = auth or current_authorization()
        domain = (
            SectionDomain.MEMENTO
            if command.type == LibraryItemType.DEVELOPMENT_CONTEXT
            else SectionDomain.RESEARCH
        )
        section_ref = await self.authorization.resolve_publish_section(
            context, command.section, domain=domain
        )
        section = await self.sections.ensure(section_ref)
        payload = command.model_dump(mode="json")
        payload["section"] = section_ref.model_dump(mode="json")
        digest = payload_hash(payload)
        if idempotency_key:
            previous = await self.receipts.get(idempotency_key, section.id, digest)
            if previous is not None:
                result = SaveResult.model_validate(previous)
                result._deduplicated = True
                return result

        item = LibraryItem(
            section=section_ref,
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
            item.attachments.append(
                await self.attachments.consume(upload_id, item.id, section_id=section.id)
            )

        slug = await self.repository.save(item)
        indexed = True
        warnings: list[str] = []
        try:
            await self.gbrain.index(item)
            await self.repository.mark_indexed(item.id)
        except Exception as exc:  # durable Markdown must survive index failures
            indexed = False
            warnings.append("Материал сохранён, но ожидает повторной индексации")
            await self.jobs.create_pending_index(item.id, str(exc), section.id)

        result = SaveResult(
            item_id=item.id, slug=slug, created=True, indexed=indexed, warnings=warnings
        )
        if idempotency_key:
            await self.receipts.save(
                idempotency_key, section.id, digest, result.model_dump(mode="json")
            )
        return result

    async def _load(self, item_id_or_slug: str) -> tuple[LibraryItem, str]:
        result = await self.repository.get(item_id_or_slug)
        if result is None:
            raise NotFoundError(f"Library item not found: {item_id_or_slug}")
        return result

    async def get(
        self,
        item_id_or_slug: str,
        *,
        auth: AuthorizationContext | None = None,
    ) -> tuple[LibraryItem, str]:
        item, slug = await self._load(item_id_or_slug)
        context = auth or current_authorization()
        await self.authorization.require_read(context, item.section)
        visible_relations = []
        for relation in item.related:
            try:
                target, _target_slug = await self._load(relation.target_id)
            except NotFoundError:
                continue
            if await self.authorization.can_read(context, target.section):
                visible_relations.append(relation)
        return item.model_copy(update={"related": visible_relations}), slug

    async def get_internal(self, item_id_or_slug: str) -> tuple[LibraryItem, str]:
        return await self.get(
            item_id_or_slug, auth=self.authorization.system_context()
        )

    async def add_relation(
        self,
        source_id: str,
        relation: Relation,
        *,
        auth: AuthorizationContext | None = None,
    ) -> tuple[LibraryItem, str]:
        context = auth or current_authorization()
        item, slug = await self._load(source_id)
        await self.authorization.require_read(context, item.section)
        await self.authorization.require_publish(context, item.section)
        await self.get(relation.target_id, auth=context)
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
