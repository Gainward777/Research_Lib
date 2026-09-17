from controllers.utils.infrastructure.gbrain.adapter import GBrainAdapter
from controllers.utils.services.access.authorization_service import AuthorizationService
from controllers.utils.services.access.context import current_authorization
from errors import PermissionDeniedError
from models.access import AuthorizationContext, SectionRef
from models.commands import SearchCommand
from models.results import AnswerResult, SearchHit


class SearchService:
    def __init__(
        self, gbrain: GBrainAdapter, authorization: AuthorizationService
    ) -> None:
        self.gbrain = gbrain
        self.authorization = authorization

    async def search(
        self,
        command: SearchCommand,
        *,
        auth: AuthorizationContext | None = None,
    ) -> list[SearchHit]:
        context = auth or current_authorization()
        sections = await self.authorization.resolve_readable_sections(
            context, command.sections or None
        )
        merged: dict[str, SearchHit] = {}
        for section in sections:
            scoped = command.model_copy(
                update={
                    "sections": [section.ref],
                    "tags": list(dict.fromkeys([*command.tags, section.ref.tag])),
                    "limit": command.limit,
                }
            )
            for hit in await self.gbrain.search(scoped):
                key = hit.item_id or hit.slug
                if key not in merged or hit.score > merged[key].score:
                    merged[key] = hit
        return sorted(
            merged.values(), key=lambda hit: (-hit.score, hit.title.casefold())
        )[: command.limit]

    async def ask(
        self,
        command: SearchCommand,
        *,
        auth: AuthorizationContext | None = None,
    ) -> AnswerResult:
        context = auth or current_authorization()
        sections = await self.authorization.resolve_readable_sections(
            context, command.sections or None
        )
        if not self.authorization.settings.library_auth_enabled and not command.sections:
            default = SectionRef.parse(
                self.authorization.settings.library_default_research_section
            )
            sections = [section for section in sections if section.ref == default]
        if len(sections) != 1:
            raise PermissionDeniedError(
                "Ask requires exactly one readable section; specify section explicitly"
            )
        scoped = command.model_copy(
            update={
                "sections": [sections[0].ref],
                "tags": list(dict.fromkeys([*command.tags, sections[0].ref.tag])),
            }
        )
        return await self.gbrain.think(scoped)
