import json
from typing import Any

from controllers.utils.infrastructure.llm.openai_responses import OpenAIResponsesClient
from controllers.utils.skills.models import RouterDecision, RouterInput
from controllers.utils.skills.registry import SkillRegistry
from models.enums import LibraryItemType


class NaturalLanguageRouter:
    """Selects one registered skill; it never executes skills or produces user answers."""

    def __init__(self, client: OpenAIResponsesClient, registry: SkillRegistry) -> None:
        self.client = client
        self.registry = registry

    async def route(self, router_input: RouterInput) -> RouterDecision:
        raw = await self.client.create_structured_response(
            system_prompt=self._system_prompt(),
            input_text=router_input.model_dump_json(),
            schema=self._decision_schema(),
        )
        decision = RouterDecision.model_validate(raw)
        if decision.kind == "invoke":
            self.registry.get(str(decision.skill_name))
        return decision

    def _system_prompt(self) -> str:
        catalog = json.dumps(self.registry.catalog(), ensure_ascii=False, indent=2)
        return (
            "You are the intent router for a Telegram research librarian. "
            "Return only the requested structured decision. Never answer the user, never search, "
            "and never save anything yourself. Choose exactly one registered skill or request a "
            "clarification for ambiguous intent. A normal knowledge question must use "
            "ask_library. An explicit request to find/list matching stored materials uses "
            "search_library. Any clearly stated report, including one written directly to the bot "
            "or forwarded from another chat, must use save_material. Reports may include text, "
            "photos, albums, and documents. Never silently save or ask on ambiguous input. "
            "collect_material starts a multi-message collection; while collection_active is true, "
            "content normally uses append_collection, an explicit finish request uses "
            "finish_collection, and an explicit cancellation uses cancel_collection. Preserve the "
            "meaning of the original text; the application will pass the exact original question "
            "to GBrain and the exact original report to storage. Use null for unused arguments. "
            f"Registered skills:\n{catalog}"
        )

    def _decision_schema(self) -> dict[str, Any]:
        nullable_string = {"anyOf": [{"type": "string"}, {"type": "null"}]}
        material_types = [item.value for item in LibraryItemType]
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "kind": {"type": "string", "enum": ["invoke", "clarify"]},
                "skill_name": {
                    "anyOf": [
                        {"type": "string", "enum": self.registry.names},
                        {"type": "null"},
                    ]
                },
                "arguments": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "query": nullable_string,
                        "title": nullable_string,
                        "material_type": {
                            "anyOf": [
                                {"type": "string", "enum": material_types},
                                {"type": "null"},
                            ]
                        },
                        "item_ref": nullable_string,
                        "requested_type": nullable_string,
                        "text": nullable_string,
                    },
                    "required": [
                        "query",
                        "title",
                        "material_type",
                        "item_ref",
                        "requested_type",
                        "text",
                    ],
                },
                "clarification_question": nullable_string,
            },
            "required": ["kind", "skill_name", "arguments", "clarification_question"],
        }
