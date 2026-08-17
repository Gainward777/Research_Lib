from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from controllers.utils.skills.models import SkillArguments, SkillContext

SkillHandler = Callable[[SkillArguments, SkillContext], Awaitable[str]]


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    description: str
    handler: SkillHandler
    arguments: dict[str, str] = field(default_factory=dict)
    accepts_attachments: bool = False

    def routing_description(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "arguments": self.arguments,
            "accepts_attachments": self.accepts_attachments,
        }


class SkillRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, SkillDefinition] = {}

    def register(self, definition: SkillDefinition) -> None:
        if definition.name in self._definitions:
            raise ValueError(f"Skill is already registered: {definition.name}")
        self._definitions[definition.name] = definition

    @property
    def names(self) -> list[str]:
        return list(self._definitions)

    def catalog(self) -> list[dict[str, object]]:
        return [definition.routing_description() for definition in self._definitions.values()]

    def get(self, name: str) -> SkillDefinition:
        try:
            return self._definitions[name]
        except KeyError as exc:
            raise ValueError(f"Unknown library skill: {name}") from exc

    async def execute(self, name: str, arguments: SkillArguments, context: SkillContext) -> str:
        return await self.get(name).handler(arguments, context)
