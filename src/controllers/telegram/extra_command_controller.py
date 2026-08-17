from aiogram.types import Message

from controllers.telegram.action_controller import invoke_registered_skill
from controllers.telegram.command_controller import command_argument
from controllers.utils.bootstrap.dependencies import ApplicationContainer
from controllers.utils.skills.models import SkillArguments
from models.enums import LibraryItemType


async def paper_command(message: Message, container: ApplicationContainer) -> str:
    value = command_argument(message)
    return await invoke_registered_skill(
        [message],
        container,
        "save_material",
        SkillArguments(material_type=LibraryItemType.PUBLICATION),
        text=value,
    )


async def item_command(message: Message, container: ApplicationContainer) -> str:
    value = command_argument(message)
    return await invoke_registered_skill(
        [message], container, "get_library_item", SkillArguments(item_ref=value or None), text=value
    )


async def related_command(message: Message, container: ApplicationContainer) -> str:
    value = command_argument(message)
    return await invoke_registered_skill(
        [message],
        container,
        "get_related_items",
        SkillArguments(item_ref=value or None),
        text=value,
    )


async def recent_command(message: Message, container: ApplicationContainer) -> str:
    requested_type = command_argument(message)
    return await invoke_registered_skill(
        [message],
        container,
        "list_recent_items",
        SkillArguments(requested_type=requested_type or None),
        text=requested_type,
    )


async def schema_command(message: Message, container: ApplicationContainer) -> str:
    return await invoke_registered_skill([message], container, "list_schema_proposals", text="")


async def health_command(message: Message, container: ApplicationContainer) -> str:
    return await invoke_registered_skill([message], container, "check_library_health", text="")


async def collect_command(message: Message, container: ApplicationContainer) -> str:
    return await invoke_registered_skill([message], container, "collect_material", text="")


async def cancel_command(message: Message, container: ApplicationContainer) -> str:
    return await invoke_registered_skill([message], container, "cancel_collection", text="")


async def save_collection_command(message: Message, container: ApplicationContainer) -> str:
    direct_text = command_argument(message)
    if await container.collections.is_active(message.chat.id):
        return await invoke_registered_skill(
            [message],
            container,
            "finish_collection",
            SkillArguments(text=direct_text or None),
            text="",
        )
    return await invoke_registered_skill(
        [message], container, "save_material", SkillArguments(), text=direct_text
    )
