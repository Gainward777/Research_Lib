from aiogram.types import Message

from controllers.utils.bootstrap.settings import Settings


def is_allowed(message: Message, settings: Settings) -> bool:
    user_id = message.from_user.id if message.from_user else None
    chat_id = message.chat.id
    user_allowed = (
        not settings.allowed_telegram_user_ids or user_id in settings.allowed_telegram_user_ids
    )
    chat_allowed = (
        not settings.allowed_telegram_chat_ids or chat_id in settings.allowed_telegram_chat_ids
    )
    return user_allowed and chat_allowed
