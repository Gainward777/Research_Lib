from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from controllers.telegram import command_controller, extra_command_controller


def message(text: str) -> SimpleNamespace:
    return SimpleNamespace(text=text, caption=None, chat=SimpleNamespace(id=10))


@pytest.mark.asyncio
async def test_every_slash_alias_dispatches_to_a_registered_skill(monkeypatch) -> None:
    core_dispatch = AsyncMock(return_value="ok")
    extra_dispatch = AsyncMock(return_value="ok")
    monkeypatch.setattr(command_controller, "invoke_registered_skill", core_dispatch)
    monkeypatch.setattr(extra_command_controller, "invoke_registered_skill", extra_dispatch)
    container = SimpleNamespace(
        collections=SimpleNamespace(is_active=AsyncMock(return_value=False))
    )

    await command_controller.search_command(message("/search LoRA"), container)
    await command_controller.ask_command(message("/ask Что известно?"), container)
    await command_controller.idea_command(message("/idea Проверить гипотезу"), container)
    await extra_command_controller.paper_command(message("/paper https://example.org"), container)
    await extra_command_controller.item_command(message("/item lib_1"), container)
    await extra_command_controller.related_command(message("/related lib_1"), container)
    await extra_command_controller.recent_command(message("/recent idea"), container)
    await extra_command_controller.schema_command(message("/schema"), container)
    await extra_command_controller.health_command(message("/health"), container)
    await extra_command_controller.collect_command(message("/collect"), container)
    await extra_command_controller.save_collection_command(message("/save Материал"), container)
    await extra_command_controller.cancel_command(message("/cancel"), container)

    names = [call.args[2] for call in core_dispatch.await_args_list]
    names.extend(call.args[2] for call in extra_dispatch.await_args_list)
    assert names == [
        "search_library",
        "ask_library",
        "save_material",
        "save_material",
        "get_library_item",
        "get_related_items",
        "list_recent_items",
        "list_schema_proposals",
        "check_library_health",
        "collect_material",
        "save_material",
        "cancel_collection",
    ]


@pytest.mark.asyncio
async def test_save_alias_finishes_active_collection(monkeypatch) -> None:
    dispatch = AsyncMock(return_value="ok")
    monkeypatch.setattr(extra_command_controller, "invoke_registered_skill", dispatch)
    container = SimpleNamespace(collections=SimpleNamespace(is_active=AsyncMock(return_value=True)))

    await extra_command_controller.save_collection_command(
        message("/save Последняя часть"), container
    )

    assert dispatch.await_args.args[2] == "finish_collection"
    assert dispatch.await_args.args[3].text == "Последняя часть"
