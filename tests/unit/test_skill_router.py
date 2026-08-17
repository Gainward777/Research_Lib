import json

import httpx
import pytest

from controllers.utils.infrastructure.llm.openai_responses import OpenAIResponsesClient
from controllers.utils.services.librarian.dialog_context import DialogTurn
from controllers.utils.skills.library import build_library_skill_registry
from controllers.utils.skills.models import (
    AttachmentMetadata,
    RouterInput,
    TelegramMetadata,
)
from controllers.utils.skills.router import NaturalLanguageRouter


def decision_payload(*, skill_name: str = "ask_library") -> dict[str, object]:
    return {
        "kind": "invoke",
        "skill_name": skill_name,
        "arguments": {
            "query": None,
            "title": None,
            "material_type": None,
            "item_ref": None,
            "requested_type": None,
            "text": None,
        },
        "clarification_question": None,
    }


@pytest.mark.asyncio
async def test_router_sends_complete_context_and_uses_strict_schema() -> None:
    captured: dict[str, object] = {}

    def respond(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(decision_payload(), ensure_ascii=False),
                            }
                        ],
                    }
                ]
            },
        )

    registry = build_library_skill_registry()
    router = NaturalLanguageRouter(
        OpenAIResponsesClient(
            "test-key",
            model="gpt-4.1-mini",
            transport=httpx.MockTransport(respond),
        ),
        registry,
    )
    router_input = RouterInput(
        original_text="Что известно о LoRA?",
        attachments=[
            AttachmentMetadata(kind="photo", file_unique_id="photo-1", width=800, height=600)
        ],
        telegram=TelegramMetadata(
            chat_id=10,
            chat_type="private",
            message_ids=[20],
            user_id=30,
            username="researcher",
            is_forwarded=True,
        ),
        dialog_context=[DialogTurn(role="assistant", text="Предыдущий ответ")],
        collection_active=False,
    )

    decision = await router.route(router_input)

    assert decision.skill_name == "ask_library"
    assert captured["model"] == "gpt-4.1-mini"
    assert captured["store"] is False
    response_format = captured["text"]["format"]
    assert response_format["strict"] is True
    assert set(response_format["schema"]["properties"]["skill_name"]["anyOf"][0]["enum"]) == set(
        registry.names
    )
    routed_input = json.loads(captured["input"][1]["content"][0]["text"])
    assert routed_input["original_text"] == router_input.original_text
    assert routed_input["attachments"][0]["kind"] == "photo"
    assert routed_input["telegram"]["is_forwarded"] is True
    assert routed_input["dialog_context"][0]["text"] == "Предыдущий ответ"


@pytest.mark.asyncio
async def test_router_rejects_unregistered_skill() -> None:
    def respond(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    decision_payload(skill_name="delete_everything")
                                ),
                            }
                        ],
                    }
                ]
            },
        )

    registry = build_library_skill_registry()
    router = NaturalLanguageRouter(
        OpenAIResponsesClient(
            "test-key",
            model="gpt-4.1-mini",
            transport=httpx.MockTransport(respond),
        ),
        registry,
    )
    router_input = RouterInput(
        original_text="Удалить всё",
        telegram=TelegramMetadata(chat_id=1, chat_type="private", message_ids=[2]),
    )

    with pytest.raises(ValueError, match="Unknown library skill"):
        await router.route(router_input)
