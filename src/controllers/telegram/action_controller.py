from collections.abc import Sequence

from aiogram.types import Message

from controllers.telegram.media_controller import upload_message_media
from controllers.utils.bootstrap.dependencies import ApplicationContainer
from controllers.utils.skills.models import (
    AttachmentMetadata,
    RouterInput,
    SkillArguments,
    SkillContext,
    TelegramMetadata,
)


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def original_text(messages: Sequence[Message]) -> str:
    parts = [message.text or message.caption or "" for message in messages]
    return "\n\n".join(part for part in parts if part)


def telegram_metadata(messages: Sequence[Message]) -> TelegramMetadata:
    if not messages:
        raise ValueError("At least one Telegram message is required")
    ordered = sorted(messages, key=lambda message: message.message_id)
    first = ordered[0]
    user = first.from_user
    return TelegramMetadata(
        chat_id=first.chat.id,
        chat_type=_enum_value(first.chat.type),
        message_ids=[message.message_id for message in ordered],
        user_id=user.id if user else None,
        username=user.username if user else None,
        is_forwarded=any(message.forward_origin is not None for message in ordered),
        media_group_id=str(first.media_group_id) if first.media_group_id else None,
    )


def attachment_metadata(messages: Sequence[Message]) -> list[AttachmentMetadata]:
    attachments: list[AttachmentMetadata] = []
    for message in messages:
        if message.photo:
            photo = message.photo[-1]
            attachments.append(
                AttachmentMetadata(
                    kind="photo",
                    file_unique_id=photo.file_unique_id,
                    mime_type="image/jpeg",
                    size_bytes=photo.file_size,
                    width=photo.width,
                    height=photo.height,
                )
            )
        elif message.document:
            document = message.document
            attachments.append(
                AttachmentMetadata(
                    kind="document",
                    file_unique_id=document.file_unique_id,
                    file_name=document.file_name,
                    mime_type=document.mime_type,
                    size_bytes=document.file_size,
                )
            )
    return attachments


async def _build_context(
    messages: Sequence[Message],
    container: ApplicationContainer,
    *,
    text: str,
    invocation_source: str,
    upload_ids: list[str] | None = None,
) -> SkillContext:
    metadata = telegram_metadata(messages)
    dialog = await container.dialog_context.recent(metadata.chat_id)
    return SkillContext(
        container=container,
        original_text=text,
        telegram=metadata,
        attachments=attachment_metadata(messages),
        attachment_upload_ids=upload_ids or [],
        dialog_context=dialog,
        collection_active=await container.collections.is_active(metadata.chat_id),
        invocation_source=invocation_source,
    )


async def invoke_registered_skill(
    messages: Sequence[Message],
    container: ApplicationContainer,
    skill_name: str,
    arguments: SkillArguments | None = None,
    *,
    text: str | None = None,
    invocation_source: str = "alias",
) -> str:
    message_list = list(messages)
    current_text = original_text(message_list) if text is None else text
    definition = container.skills.get(skill_name)
    uploaded: list[str] = []
    if definition.accepts_attachments and attachment_metadata(message_list):
        uploaded = await upload_message_media(message_list, container)
    context = await _build_context(
        message_list,
        container,
        text=current_text,
        invocation_source=invocation_source,
        upload_ids=uploaded,
    )
    try:
        response = await container.skills.execute(
            skill_name,
            arguments or SkillArguments(),
            context,
        )
    except Exception:
        for upload_id in uploaded:
            await container.attachments.discard(upload_id)
        raise
    await container.dialog_context.add_exchange(context.telegram.chat_id, current_text, response)
    return response


async def route_natural_messages(
    messages: Sequence[Message], container: ApplicationContainer
) -> str:
    message_list = sorted(messages, key=lambda message: message.message_id)
    current_text = original_text(message_list)
    context = await _build_context(
        message_list,
        container,
        text=current_text,
        invocation_source="natural",
    )
    decision = await container.router.route(
        RouterInput(
            original_text=current_text,
            attachments=context.attachments,
            telegram=context.telegram,
            dialog_context=context.dialog_context,
            collection_active=context.collection_active,
        )
    )
    if decision.kind == "clarify":
        response = str(decision.clarification_question)
        await container.dialog_context.add_exchange(
            context.telegram.chat_id, current_text, response
        )
        return response
    return await invoke_registered_skill(
        message_list,
        container,
        str(decision.skill_name),
        decision.arguments,
        text=current_text,
        invocation_source="natural",
    )
