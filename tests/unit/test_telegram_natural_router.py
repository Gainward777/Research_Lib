from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from controllers.telegram import action_controller
from controllers.utils.skills.models import RouterDecision, SkillArguments
from controllers.utils.skills.registry import SkillDefinition, SkillRegistry


def telegram_message(*, text: str = "", forwarded: bool = False, photo: bool = False):
    photo_value = []
    if photo:
        photo_value = [
            SimpleNamespace(
                file_unique_id="photo-unique",
                file_size=123,
                width=800,
                height=600,
            )
        ]
    return SimpleNamespace(
        message_id=20,
        text=text or None,
        caption=None,
        chat=SimpleNamespace(id=10, type="private"),
        from_user=SimpleNamespace(id=30, username="researcher"),
        forward_origin=SimpleNamespace() if forwarded else None,
        media_group_id=None,
        photo=photo_value,
        document=None,
    )


def fake_container(registry: SkillRegistry, decision: RouterDecision):
    return SimpleNamespace(
        skills=registry,
        router=SimpleNamespace(route=AsyncMock(return_value=decision)),
        collections=SimpleNamespace(is_active=AsyncMock(return_value=False)),
        dialog_context=SimpleNamespace(
            recent=AsyncMock(return_value=[]),
            add_exchange=AsyncMock(),
        ),
        attachments=SimpleNamespace(discard=AsyncMock()),
    )


@pytest.mark.asyncio
async def test_ambiguous_intent_requests_clarification_without_executing_skill(monkeypatch) -> None:
    handler = AsyncMock(return_value="must not run")
    registry = SkillRegistry()
    registry.register(SkillDefinition("save_material", "save", handler, accepts_attachments=True))
    decision = RouterDecision(
        kind="clarify",
        skill_name=None,
        arguments=SkillArguments(),
        clarification_question="Вы хотите сохранить это или задать вопрос?",
    )
    container = fake_container(registry, decision)
    upload = AsyncMock(return_value=["upload-1"])
    monkeypatch.setattr(action_controller, "upload_message_media", upload)

    response = await action_controller.route_natural_messages(
        [telegram_message(text="Неоднозначный текст", photo=True)], container
    )

    assert response == "Вы хотите сохранить это или задать вопрос?"
    handler.assert_not_awaited()
    upload.assert_not_awaited()


@pytest.mark.asyncio
async def test_forwarded_report_with_photo_reaches_save_material(monkeypatch) -> None:
    handler = AsyncMock(return_value="saved")
    registry = SkillRegistry()
    registry.register(SkillDefinition("save_material", "save", handler, accepts_attachments=True))
    decision = RouterDecision(
        kind="invoke",
        skill_name="save_material",
        arguments=SkillArguments(material_type="experiment-report"),
        clarification_question=None,
    )
    container = fake_container(registry, decision)
    upload = AsyncMock(return_value=["upload-1"])
    monkeypatch.setattr(action_controller, "upload_message_media", upload)
    report = "Отчёт: метрика выросла"

    response = await action_controller.route_natural_messages(
        [telegram_message(text=report, forwarded=True, photo=True)], container
    )

    assert response == "saved"
    routed_input = container.router.route.await_args.args[0]
    assert routed_input.original_text == report
    assert routed_input.telegram.is_forwarded is True
    assert routed_input.attachments[0].kind == "photo"
    context = handler.await_args.args[1]
    assert context.original_text == report
    assert context.attachment_upload_ids == ["upload-1"]
