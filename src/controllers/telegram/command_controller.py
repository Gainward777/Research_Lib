from aiogram.types import Message

from controllers.utils.bootstrap.dependencies import ApplicationContainer
from models.commands import CreateItemCommand, SearchCommand
from models.enums import LibraryItemType, SourceKind
from views.telegram.answer_view import render_answer
from views.telegram.receipt_view import render_saved
from views.telegram.search_view import render_search


def command_argument(message: Message) -> str:
    text = message.text or ""
    return text.split(maxsplit=1)[1].strip() if len(text.split(maxsplit=1)) == 2 else ""


async def search_command(message: Message, container: ApplicationContainer) -> str:
    query = command_argument(message)
    if not query:
        return "Использование: /search <запрос>"
    return render_search(await container.search.search(SearchCommand(query=query)))


async def ask_command(message: Message, container: ApplicationContainer) -> str:
    query = command_argument(message)
    if not query:
        return "Использование: /ask <вопрос>"
    return render_answer(await container.search.ask(SearchCommand(query=query, synthesize=True)))


async def idea_command(message: Message, container: ApplicationContainer) -> str:
    content = command_argument(message)
    if not content:
        return "Использование: /idea <текст>"
    result = await container.ingestion.ingest(
        CreateItemCommand(
            type=LibraryItemType.IDEA,
            title=content[:100],
            content=content,
            source_kind=SourceKind.TELEGRAM,
            source_external_id=f"telegram:{message.chat.id}:{message.message_id}",
        ),
        idempotency_key=f"telegram:{message.chat.id}:{message.message_id}",
    )
    return render_saved(result, content[:100])
