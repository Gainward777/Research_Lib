from io import BytesIO

from aiogram.types import Message

from controllers.utils.bootstrap.dependencies import ApplicationContainer
from controllers.utils.services.access.context import current_authorization
from models.access import SectionDomain


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
    section_ref = await container.authorization.resolve_publish_section(
        current_authorization(), None, domain=SectionDomain.RESEARCH
    )
    section = await container.sections_store.require(section_ref)
    result = await container.attachments.save_upload(
        stream.getvalue(), filename, content_type, section_id=section.id
    )
    return str(result["upload_id"])


async def upload_message_media(
    messages: list[Message], container: ApplicationContainer
) -> list[str]:
    upload_ids: list[str] = []
    for message in messages:
        upload_id = await _upload_message_media(message, container)
        if upload_id:
            upload_ids.append(upload_id)
    return upload_ids
