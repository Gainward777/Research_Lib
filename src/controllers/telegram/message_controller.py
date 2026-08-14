from aiogram.types import Message

from controllers.utils.bootstrap.dependencies import ApplicationContainer
from controllers.utils.services.ingestion.classifier import classify_material
from controllers.utils.services.librarian.intent_service import Intent, classify_intent
from models.commands import CreateItemCommand, SearchCommand
from models.enums import SourceKind
from views.telegram.answer_view import render_answer
from views.telegram.receipt_view import render_saved
from views.telegram.search_view import render_search


async def handle_message(message: Message, container: ApplicationContainer) -> str:
    text = message.text or message.caption or ""
    intent = classify_intent(
        text,
        has_attachments=bool(message.photo or message.document),
        is_forwarded=message.forward_origin is not None,
    )
    if intent is Intent.ASK:
        return render_answer(await container.search.ask(SearchCommand(query=text, synthesize=True)))
    if intent is Intent.SEARCH:
        query = text.split(maxsplit=1)[1].strip() if len(text.split(maxsplit=1)) == 2 else ""
        return render_search(await container.search.search(SearchCommand(query=query)))
    return await save_message(message, container)


async def save_message(message: Message, container: ApplicationContainer) -> str:
    text = message.text or message.caption or ""
    title = next((line.strip() for line in text.splitlines() if line.strip()), "Telegram note")
    command = CreateItemCommand(
        type=classify_material(text),
        title=title[:300],
        content=text,
        source_kind=SourceKind.TELEGRAM,
        source_external_id=f"telegram:{message.chat.id}:{message.message_id}",
    )
    result = await container.ingestion.ingest(
        command, idempotency_key=f"telegram:{message.chat.id}:{message.message_id}"
    )
    return render_saved(result, title)
