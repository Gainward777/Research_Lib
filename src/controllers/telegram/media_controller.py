from io import BytesIO

from aiogram.types import Message

from controllers.utils.bootstrap.dependencies import ApplicationContainer
from controllers.utils.services.ingestion.classifier import classify_material
from models.commands import CreateItemCommand
from models.enums import SourceKind
from views.telegram.receipt_view import render_saved


async def _upload_message_media(message: Message, container: ApplicationContainer) -> str | None:
    downloadable = None
    filename = None
    content_type = None
    if message.photo:
        photo = message.photo[-1]
        downloadable = photo
        filename = f"telegram-{photo.file_unique_id}.jpg"
        content_type = "image/jpeg"
    elif message.document:
        downloadable = message.document
        filename = message.document.file_name or f"telegram-{message.document.file_unique_id}"
        content_type = message.document.mime_type
    if downloadable is None:
        return None
    stream = BytesIO()
    await message.bot.download(downloadable, destination=stream)
    result = await container.attachments.save_upload(stream.getvalue(), filename, content_type)
    return str(result["upload_id"])


async def save_media_messages(messages: list[Message], container: ApplicationContainer) -> str:
    if not messages:
        raise ValueError("Empty Telegram media group")
    upload_ids = []
    captions = []
    for message in messages:
        if message.caption:
            captions.append(message.caption)
        upload_id = await _upload_message_media(message, container)
        if upload_id:
            upload_ids.append(upload_id)
    content = "\n\n".join(captions)
    title = next((line.strip() for line in content.splitlines() if line.strip()), "Telegram media")
    first = messages[0]
    if first.media_group_id:
        external_id = f"telegram-group:{first.chat.id}:{first.media_group_id}"
    else:
        external_id = f"telegram:{first.chat.id}:{first.message_id}"
    result = await container.ingestion.ingest(
        CreateItemCommand(
            type=classify_material(content),
            title=title[:300],
            content=content,
            source_kind=SourceKind.TELEGRAM,
            source_external_id=external_id,
            attachment_upload_ids=upload_ids,
        ),
        idempotency_key=external_id,
    )
    return render_saved(result, title)
