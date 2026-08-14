from aiogram.types import Message

from controllers.telegram.collection_store import CollectionStore
from controllers.telegram.command_controller import command_argument
from controllers.utils.bootstrap.dependencies import ApplicationContainer
from models.commands import CreateItemCommand
from models.enums import LibraryItemType, SourceKind
from views.telegram.item_view import render_item
from views.telegram.receipt_view import render_saved


async def paper_command(message: Message, container: ApplicationContainer) -> str:
    value = command_argument(message)
    if not value:
        return "Использование: /paper <url или текст>"
    result = await container.publications.save(
        value[:300],
        value,
        value if value.startswith(("http://", "https://")) else None,
        [],
        f"telegram:{message.chat.id}:{message.message_id}",
    )
    return render_saved(result, value[:300])


async def item_command(message: Message, container: ApplicationContainer) -> str:
    value = command_argument(message)
    if not value:
        return "Использование: /item <id или slug>"
    item, _slug = await container.items.get(value)
    return render_item(item)


async def related_command(message: Message, container: ApplicationContainer) -> str:
    value = command_argument(message)
    if not value:
        return "Использование: /related <id или slug>"
    item, _slug = await container.items.get(value)
    if not item.related:
        return "Связанные материалы не найдены."
    lines = []
    for relation in item.related:
        target, _target_slug = await container.items.get(relation.target_id)
        lines.append(f"- {relation.type.value}: {target.title} ({target.id})")
    return "\n".join(lines)


async def recent_command(message: Message, container: ApplicationContainer) -> str:
    requested_type = command_argument(message)
    if requested_type:
        rows = await container.database.fetchall(
            "SELECT id, type, title, slug FROM library_items WHERE type=? "
            "ORDER BY created_at DESC LIMIT 10",
            (requested_type,),
        )
    else:
        rows = await container.database.fetchall(
            "SELECT id, type, title, slug FROM library_items ORDER BY created_at DESC LIMIT 10"
        )
    if not rows:
        return "Библиотека пока пуста."
    return "\n".join(f"- {row['title']} [{row['type']}] ({row['id']})" for row in rows)


async def schema_command(_message: Message, container: ApplicationContainer) -> str:
    proposals = await container.proposals.list()
    pending = [item for item in proposals if item["status"] == "pending"]
    if not pending:
        return "Новых предложений изменения схемы нет."
    return "\n".join(f"- {item['name']} [{item['kind']}] ({item['id']})" for item in pending)


async def health_command(_message: Message, container: ApplicationContainer) -> str:
    return "Библиотека готова." if await container.gbrain.health() else "GBrain недоступен."


async def collect_command(message: Message, container: ApplicationContainer) -> str:
    await CollectionStore(container.database).start(message.chat.id)
    return "Сбор начат. Отправляйте сообщения, затем вызовите /save или /cancel."


async def cancel_command(message: Message, container: ApplicationContainer) -> str:
    await CollectionStore(container.database).cancel(message.chat.id)
    return "Сбор отменён."


async def save_collection_command(message: Message, container: ApplicationContainer) -> str:
    direct_text = command_argument(message)
    if direct_text:
        parts = [direct_text]
    else:
        parts = await CollectionStore(container.database).pop(message.chat.id)
    if not parts:
        return "Нет материалов для сохранения."
    content = "\n\n".join(parts)
    title = next((line.strip() for line in content.splitlines() if line.strip()), "Collection")
    result = await container.ingestion.ingest(
        CreateItemCommand(
            type=LibraryItemType.NOTE,
            title=title[:300],
            content=content,
            source_kind=SourceKind.TELEGRAM,
            source_external_id=f"telegram:{message.chat.id}:{message.message_id}",
        ),
        idempotency_key=f"telegram:{message.chat.id}:{message.message_id}",
    )
    return render_saved(result, title)
