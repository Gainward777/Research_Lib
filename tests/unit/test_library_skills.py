from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from controllers.utils.bootstrap.dependencies import build_container
from controllers.utils.bootstrap.settings import Settings
from controllers.utils.skills.library import build_library_skill_registry
from controllers.utils.skills.models import SkillArguments, SkillContext, TelegramMetadata
from models.enums import LibraryItemType
from models.results import AnswerResult, SaveResult
from tests.fakes import FakeGBrainAdapter


def skill_context(container, text: str, upload_ids: list[str] | None = None) -> SkillContext:
    return SkillContext(
        container=container,
        original_text=text,
        telegram=TelegramMetadata(chat_id=10, chat_type="private", message_ids=[20]),
        attachment_upload_ids=upload_ids or [],
    )


def test_all_telegram_actions_are_registered() -> None:
    names = set(build_library_skill_registry().names)
    assert {
        "ask_library",
        "search_library",
        "save_material",
        "collect_material",
        "append_collection",
        "finish_collection",
        "cancel_collection",
        "get_library_item",
        "get_related_items",
        "list_recent_items",
        "list_schema_proposals",
        "check_library_health",
    } <= names


@pytest.mark.asyncio
async def test_ask_library_returns_gbrain_answer_and_question_exactly(tmp_path: Path) -> None:
    container = await build_container(
        Settings(library_data_root=tmp_path / "library"),
        gbrain_factory=FakeGBrainAdapter,
    )
    try:
        container.search.ask = AsyncMock(
            return_value=AnswerResult(answer="  Ответ GBrain.\nВторая строка.  ")
        )
        question = "  Каков результат?\n"

        response = await container.skills.execute(
            "ask_library",
            SkillArguments(query="переформулированный вопрос"),
            skill_context(container, question),
        )

        command = container.search.ask.await_args.args[0]
        assert command.query == question
        assert response == "  Ответ GBrain.\nВторая строка.  "
    finally:
        await container.close()


@pytest.mark.asyncio
async def test_report_and_attachments_are_saved_only_through_save_material(tmp_path: Path) -> None:
    container = await build_container(
        Settings(library_data_root=tmp_path / "library"),
        gbrain_factory=FakeGBrainAdapter,
    )
    try:
        container.ingestion.ingest = AsyncMock(
            return_value=SaveResult(
                item_id="lib_report", slug="reports/report", created=True, indexed=True
            )
        )
        report = "Отчёт\nГипотеза: A\nВывод: B"

        await container.skills.execute(
            "save_material",
            SkillArguments(),
            skill_context(container, report, ["upload-photo", "upload-document"]),
        )

        command = container.ingestion.ingest.await_args.args[0]
        assert command.type is LibraryItemType.EXPERIMENT_REPORT
        assert command.content == report
        assert command.attachment_upload_ids == ["upload-photo", "upload-document"]
    finally:
        await container.close()


@pytest.mark.asyncio
async def test_finish_collection_saves_one_combined_material(tmp_path: Path) -> None:
    container = await build_container(
        Settings(library_data_root=tmp_path / "library"),
        gbrain_factory=FakeGBrainAdapter,
    )
    try:
        container.ingestion.ingest = AsyncMock(
            return_value=SaveResult(
                item_id="lib_batch", slug="reports/batch", created=True, indexed=True
            )
        )
        await container.collections.start(10)
        await container.collections.add(10, "Первая часть", ["upload-1"])
        await container.collections.add(10, "Вторая часть", ["upload-2"])

        await container.skills.execute(
            "finish_collection",
            SkillArguments(text="текст, которого не было в сообщениях"),
            skill_context(container, "заверши сбор", ["upload-3"]),
        )

        command = container.ingestion.ingest.await_args.args[0]
        assert command.content == "Первая часть\n\nВторая часть"
        assert command.attachment_upload_ids == ["upload-1", "upload-2", "upload-3"]
        assert not await container.collections.is_active(10)
    finally:
        await container.close()
