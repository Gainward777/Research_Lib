from aiogram.types import Message

from controllers.telegram.action_controller import route_natural_messages
from controllers.utils.bootstrap.dependencies import ApplicationContainer


async def handle_message(message: Message, container: ApplicationContainer) -> str:
    return await route_natural_messages([message], container)
