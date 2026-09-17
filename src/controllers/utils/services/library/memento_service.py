from controllers.utils.services.access.context import current_authorization
from controllers.utils.services.librarian.search_service import SearchService
from controllers.utils.services.library.item_service import ItemService
from models.access import AuthorizationContext, SectionDomain, SectionRef
from models.commands import CreateItemCommand, SearchCommand
from models.enums import LibraryItemType, RelationType, SourceKind
from models.library_item import Relation
from models.memento import (
    ContextCreator,
    ContextVerification,
    DevelopmentContextBundle,
    DevelopmentContextEntry,
    DevelopmentContextKind,
    DevelopmentContextQuery,
    PublishDevelopmentContext,
)
from models.results import SaveResult

BLOCK_BY_KIND = {
    DevelopmentContextKind.IMPLEMENTATION_SNAPSHOT: "related_implementations",
    DevelopmentContextKind.DECISION: "decisions",
    DevelopmentContextKind.PROBLEM: "known_problems",
    DevelopmentContextKind.TEST_EVIDENCE: "tests_and_evidence",
    DevelopmentContextKind.CHECKPOINT: "checkpoints",
}


def _scope_tag(prefix: str, value: str) -> str:
    return f"{prefix}:{value.strip().casefold()}"


def _deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


class MementoService:
    def __init__(self, items: ItemService, search: SearchService) -> None:
        self.items = items
        self.search = search

    async def publish(
        self,
        context: PublishDevelopmentContext,
        *,
        idempotency_key: str,
        auth: AuthorizationContext | None = None,
    ) -> SaveResult:
        authorization = auth or current_authorization()
        section = SectionRef(domain=SectionDomain.MEMENTO, key=context.project)
        superseded_item_id = context.supersedes_item_id
        source_ids = _deduplicate(context.consulted_context_item_ids)
        if superseded_item_id:
            superseded, _slug = await self.items.get(
                superseded_item_id, auth=authorization
            )
            if superseded.type != LibraryItemType.DEVELOPMENT_CONTEXT:
                raise ValueError("supersedes_item_id must reference development-context")
        for source_id in source_ids:
            await self.items.get(source_id, auth=authorization)

        metadata: dict[str, object] = {
            "context_kind": context.context_kind.value,
            "project": context.project,
            "repository": context.repository,
            "work_item": context.work_item,
            "work_context_id": context.work_context_id,
            "branch": context.branch,
            "commit": context.commit,
            "paths": context.paths,
            "created_by": context.created_by.value,
            "verification": context.verification.value,
            "supersedes_item_id": superseded_item_id,
            "consulted_context_item_ids": source_ids,
        }
        tags = _deduplicate(
            [
                *context.tags,
                "memento",
                _scope_tag("project", context.project),
                _scope_tag("repository", context.repository) if context.repository else "",
                _scope_tag("kind", context.context_kind.value),
            ]
        )
        result = await self.items.create(
            CreateItemCommand(
                section=section,
                type=LibraryItemType.DEVELOPMENT_CONTEXT,
                title=context.title,
                content=context.content,
                summary=context.summary,
                source_kind=SourceKind.AGENT,
                source_external_id=context.work_item or context.work_context_id,
                tags=tags,
                metadata=metadata,
            ),
            idempotency_key=idempotency_key,
            auth=authorization,
        )
        if superseded_item_id:
            await self.items.add_relation(
                result.item_id,
                Relation(type=RelationType.CONTINUES, target_id=superseded_item_id),
                auth=authorization,
            )
        for source_id in source_ids:
            await self.items.add_relation(
                result.item_id,
                Relation(type=RelationType.HAS_SOURCE, target_id=source_id),
                auth=authorization,
            )
        return result

    async def get_context(
        self,
        request: DevelopmentContextQuery,
        *,
        auth: AuthorizationContext | None = None,
    ) -> DevelopmentContextBundle:
        authorization = auth or current_authorization()
        requested_sections = (
            [SectionRef(domain=SectionDomain.MEMENTO, key=request.project)]
            if request.project
            else [
                section.ref
                for section in await self.search.authorization.resolve_readable_sections(
                    authorization, domain=SectionDomain.MEMENTO
                )
            ]
        )
        required_tags: list[str] = []
        if request.project:
            required_tags.append(_scope_tag("project", request.project))
        if request.repository:
            required_tags.append(_scope_tag("repository", request.repository))

        hits = await self.search.search(
            SearchCommand(
                query=request.query,
                sections=requested_sections,
                types=[LibraryItemType.DEVELOPMENT_CONTEXT],
                tags=required_tags,
                limit=request.limit,
            ),
            auth=authorization,
        )
        bundle = DevelopmentContextBundle(
            query=request.query,
            project=request.project,
            repository=request.repository,
            work_item=request.work_item,
        )
        for hit in hits:
            item, slug = await self.items.get(
                hit.item_id or hit.slug, auth=authorization
            )
            raw_kind = item.metadata.get("context_kind")
            try:
                kind = DevelopmentContextKind(str(raw_kind))
            except ValueError:
                continue
            entry = DevelopmentContextEntry(
                item_id=item.id,
                slug=slug,
                context_kind=kind,
                title=item.title,
                content=item.content,
                summary=item.summary,
                project=str(item.metadata.get("project") or ""),
                repository=str(item.metadata.get("repository") or ""),
                work_item=_optional_string(item.metadata.get("work_item")),
                work_context_id=_optional_string(item.metadata.get("work_context_id")),
                branch=_optional_string(item.metadata.get("branch")),
                commit=_optional_string(item.metadata.get("commit")),
                paths=[str(path) for path in item.metadata.get("paths") or []],
                created_by=ContextCreator(
                    str(item.metadata.get("created_by") or ContextCreator.AGENT)
                ),
                verification=ContextVerification(
                    str(item.metadata.get("verification") or ContextVerification.UNVERIFIED)
                ),
                supersedes_item_id=_optional_string(item.metadata.get("supersedes_item_id")),
                created_at=item.created_at,
                score=hit.score,
                consulted_context_item_ids=[
                    str(value) for value in item.metadata.get("consulted_context_item_ids") or []
                ],
            )
            getattr(bundle, BLOCK_BY_KIND[kind]).append(entry)
        return bundle


def _optional_string(value: object) -> str | None:
    return str(value) if value not in (None, "") else None
