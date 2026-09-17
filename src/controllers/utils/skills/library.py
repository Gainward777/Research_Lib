from controllers.utils.services.access.context import current_authorization
from controllers.utils.services.ingestion.classifier import classify_material
from controllers.utils.skills.models import SkillArguments, SkillContext
from controllers.utils.skills.registry import SkillDefinition, SkillRegistry
from errors import NotFoundError
from models.commands import CreateItemCommand, SearchCommand
from models.enums import LibraryItemType, SourceKind
from views.telegram.item_view import render_item
from views.telegram.receipt_view import render_saved
from views.telegram.search_view import render_search


def _first_nonempty_line(text: str, fallback: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), fallback)


async def _discard_uploads(upload_ids: list[str], context: SkillContext) -> None:
    for upload_id in upload_ids:
        await context.container.attachments.discard(upload_id)


async def ask_library(_arguments: SkillArguments, context: SkillContext) -> str:
    question = context.original_text
    if not question:
        return "Использование: /ask <вопрос>"
    result = await context.container.search.ask(SearchCommand(query=question, synthesize=True))
    return result.answer


async def search_library(arguments: SkillArguments, context: SkillContext) -> str:
    query = arguments.query or context.original_text
    if not query:
        return "Использование: /search <запрос>"
    return render_search(await context.container.search.search(SearchCommand(query=query)))


async def save_material(arguments: SkillArguments, context: SkillContext) -> str:
    content = context.original_text
    upload_ids = context.attachment_upload_ids
    if not content and not upload_ids:
        return "Нет материала для сохранения."
    item_type = arguments.material_type or classify_material(content)
    title = (arguments.title or _first_nonempty_line(content, "Медиа из Telegram"))[:300]
    metadata: dict[str, object] = {
        "telegram_chat_id": context.telegram.chat_id,
        "telegram_message_ids": context.telegram.message_ids,
    }
    if item_type is LibraryItemType.PUBLICATION and content.startswith(("http://", "https://")):
        metadata["url"] = content
    result = await context.container.ingestion.ingest(
        CreateItemCommand(
            type=item_type,
            title=title,
            content=content,
            source_kind=SourceKind.TELEGRAM,
            source_external_id=context.source_external_id,
            attachment_upload_ids=upload_ids,
            metadata=metadata,
        ),
        idempotency_key=context.source_external_id,
    )
    return render_saved(result, title)


async def collect_material(_arguments: SkillArguments, context: SkillContext) -> str:
    previous = await context.container.collections.pop_material(context.telegram.chat_id)
    await _discard_uploads(previous.upload_ids, context)
    await context.container.collections.start(context.telegram.chat_id)
    return (
        "Сбор начат. Отправляйте сообщения и вложения, затем попросите завершить сбор "
        "или используйте /save."
    )


async def append_collection(_arguments: SkillArguments, context: SkillContext) -> str:
    if not context.collection_active:
        return "Сбор не начат. Сначала попросите начать сбор или используйте /collect."
    if not context.original_text and not context.attachment_upload_ids:
        return "В сообщении нет материала для добавления."
    count = await context.container.collections.add(
        context.telegram.chat_id,
        context.original_text,
        context.attachment_upload_ids,
    )
    return f"Добавлено в сбор: {count}"


async def cancel_collection(_arguments: SkillArguments, context: SkillContext) -> str:
    material = await context.container.collections.pop_material(context.telegram.chat_id)
    await _discard_uploads(material.upload_ids, context)
    return "Сбор отменён."


async def get_library_item(arguments: SkillArguments, context: SkillContext) -> str:
    item_ref = arguments.item_ref or context.original_text
    if not item_ref:
        return "Использование: /item <id или slug>"
    item, _slug = await context.container.items.get(item_ref)
    return render_item(item)


async def get_related_items(arguments: SkillArguments, context: SkillContext) -> str:
    item_ref = arguments.item_ref or context.original_text
    if not item_ref:
        return "Использование: /related <id или slug>"
    item, _slug = await context.container.items.get(item_ref)
    if not item.related:
        return "Связанные материалы не найдены."
    lines = []
    for relation in item.related:
        try:
            target, _target_slug = await context.container.items.get(relation.target_id)
        except NotFoundError:
            continue
        lines.append(f"- {relation.type.value}: {target.title} ({target.id})")
    return "\n".join(lines)


async def list_recent_items(arguments: SkillArguments, context: SkillContext) -> str:
    requested_type = arguments.requested_type
    if requested_type:
        rows = await context.container.database.fetchall(
            "SELECT id FROM library_items WHERE type=? "
            "ORDER BY created_at DESC LIMIT 100",
            (requested_type,),
        )
    else:
        rows = await context.container.database.fetchall(
            "SELECT id FROM library_items ORDER BY created_at DESC LIMIT 100"
        )
    visible = []
    for row in rows:
        try:
            item, _slug = await context.container.items.get(str(row["id"]))
        except NotFoundError:
            continue
        visible.append(item)
        if len(visible) == 10:
            break
    if not visible:
        return "Библиотека пока пуста."
    return "\n".join(
        f"- {item.title} [{item.type.value}] ({item.id})" for item in visible
    )

async def list_schema_proposals(_arguments: SkillArguments, context: SkillContext) -> str:
    await context.container.authorization.require_admin(current_authorization())
    proposals = await context.container.proposals.list()
    pending = [item for item in proposals if item["status"] == "pending"]
    if not pending:
        return "Новых предложений изменения схемы нет."
    return "\n".join(f"- {item['name']} [{item['kind']}] ({item['id']})" for item in pending)


async def check_library_health(_arguments: SkillArguments, context: SkillContext) -> str:
    return "Библиотека готова." if await context.container.gbrain.health() else "GBrain недоступен."


def build_library_skill_registry() -> SkillRegistry:
    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            name="ask_library",
            description="Ответить на вопрос на естественном языке через GBrain think.",
            arguments={"query": "Вопрос; приложение передаст original_text без изменений."},
            handler=ask_library,
        )
    )
    registry.register(
        SkillDefinition(
            name="search_library",
            description="Найти подходящие сохранённые материалы без синтеза ответа.",
            arguments={"query": "Краткий поисковый запрос."},
            handler=search_library,
        )
    )
    registry.register(
        SkillDefinition(
            name="save_material",
            description=(
                "Сохранить один отчёт, заметку, идею, публикацию, альбом или набор документов."
            ),
            arguments={
                "title": "Необязательный заголовок.",
                "material_type": "Необязательный тип материала библиотеки.",
            },
            handler=save_material,
            accepts_attachments=True,
        )
    )
    registry.register(
        SkillDefinition(
            name="collect_material",
            description="Начать сбор следующих сообщений и вложений в один материал.",
            handler=collect_material,
        )
    )
    registry.register(
        SkillDefinition(
            name="append_collection",
            description="Добавить текущее сообщение в активный сбор материала.",
            handler=append_collection,
            accepts_attachments=True,
        )
    )

    async def finish_collection(arguments: SkillArguments, context: SkillContext) -> str:
        material = await context.container.collections.pop_material(context.telegram.chat_id)
        text_parts = list(material.text_parts)
        if context.invocation_source == "alias" and arguments.text:
            text_parts.append(arguments.text)
        upload_ids = [*material.upload_ids, *context.attachment_upload_ids]
        if not text_parts and not upload_ids:
            return "Нет материалов для сохранения."
        combined_context = SkillContext(
            container=context.container,
            original_text="\n\n".join(text_parts),
            telegram=context.telegram,
            attachments=context.attachments,
            attachment_upload_ids=upload_ids,
            dialog_context=context.dialog_context,
            collection_active=False,
            invocation_source=context.invocation_source,
        )
        return await registry.execute("save_material", SkillArguments(), combined_context)

    registry.register(
        SkillDefinition(
            name="finish_collection",
            description="Завершить активный сбор и сохранить все части через save_material.",
            arguments={"text": "Необязательный финальный текст из slash-команды."},
            handler=finish_collection,
            accepts_attachments=True,
        )
    )
    registry.register(
        SkillDefinition(
            name="cancel_collection",
            description="Отменить активный сбор и удалить его несохранённые вложения.",
            handler=cancel_collection,
        )
    )
    registry.register(
        SkillDefinition(
            name="get_library_item",
            description="Открыть сохранённый материал по постоянному ID или slug.",
            arguments={"item_ref": "ID или slug материала."},
            handler=get_library_item,
        )
    )
    registry.register(
        SkillDefinition(
            name="get_related_items",
            description="Показать связи сохранённого материала.",
            arguments={"item_ref": "ID или slug материала."},
            handler=get_related_items,
        )
    )
    registry.register(
        SkillDefinition(
            name="list_recent_items",
            description="Показать десять последних материалов с необязательным фильтром по типу.",
            arguments={"requested_type": "Необязательный тип материала."},
            handler=list_recent_items,
        )
    )
    registry.register(
        SkillDefinition(
            name="list_schema_proposals",
            description="Показать ожидающие предложения по изменению исследовательской схемы.",
            handler=list_schema_proposals,
        )
    )
    registry.register(
        SkillDefinition(
            name="check_library_health",
            description="Проверить готовность библиотеки на базе GBrain.",
            handler=check_library_health,
        )
    )
    return registry
