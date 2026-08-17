import re

from aiogram.types import Message

from controllers.telegram.action_controller import invoke_registered_skill
from controllers.utils.bootstrap.dependencies import ApplicationContainer
from controllers.utils.skills.models import SkillArguments
from models.enums import LibraryItemType


def command_argument(message: Message) -> str:
    text = message.text or message.caption or ""
    match = re.match(r"^\S+\s+(.*)$", text, flags=re.DOTALL)
    return match.group(1) if match else ""


async def search_command(message: Message, container: ApplicationContainer) -> str:
    query = command_argument(message)
    return await invoke_registered_skill(
        [message], container, "search_library", SkillArguments(query=query or None), text=query
    )


async def ask_command(message: Message, container: ApplicationContainer) -> str:
    question = command_argument(message)
    return await invoke_registered_skill(
        [message], container, "ask_library", SkillArguments(query=question or None), text=question
    )


async def idea_command(message: Message, container: ApplicationContainer) -> str:
    content = command_argument(message)
    return await invoke_registered_skill(
        [message],
        container,
        "save_material",
        SkillArguments(material_type=LibraryItemType.IDEA),
        text=content,
    )
