import json
import re
from typing import Any

from controllers.utils.infrastructure.llm.openai_responses import OpenAIResponsesClient
from controllers.utils.skills.models import RouterDecision, RouterInput
from controllers.utils.skills.registry import SkillRegistry
from models.enums import LibraryItemType

DEFAULT_CLARIFICATION_QUESTION = (
    "Уточните, пожалуйста: вы хотите сохранить материал, найти материалы "
    "или задать вопрос библиотеке?"
)


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
        elif not re.search(r"[А-Яа-яЁё]", str(decision.clarification_question)):
            decision = decision.model_copy(
                update={"clarification_question": DEFAULT_CLARIFICATION_QUESTION}
            )
        return decision

    def _system_prompt(self) -> str:
        catalog = json.dumps(self.registry.catalog(), ensure_ascii=False, indent=2)
        return (
            "Ты — маршрутизатор намерений Telegram-бота-библиотекаря. "
            "Возвращай только запрошенное структурированное решение. Сам не отвечай "
            "пользователю, не выполняй поиск и ничего не сохраняй. Выбери ровно один "
            "зарегистрированный скилл, а при неоднозначном намерении запроси уточнение. "
            "Любой уточняющий вопрос формулируй только на русском языке. Обычный вопрос "
            "о знаниях направляй в ask_library. Явную просьбу найти или перечислить "
            "подходящие сохранённые материалы направляй в search_library. Любой явно "
            "сформулированный отчёт, написанный боту или пересланный из другого чата, "
            "направляй в save_material. Отчёт может содержать текст, фотографии, альбомы "
            "и документы. При неоднозначности не сохраняй материал и не задавай вопрос "
            "библиотеке молча. collect_material начинает сбор нескольких сообщений; когда "
            "collection_active=true, очередной материал обычно направляется в "
            "append_collection, явное завершение — в finish_collection, отмена — в "
            "cancel_collection. Сохраняй смысл исходного текста: приложение передаст "
            "GBrain точный исходный вопрос, а в хранилище — точный исходный отчёт. "
            "Для неиспользуемых аргументов указывай null. "
            f"Зарегистрированные скиллы:\n{catalog}"
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
