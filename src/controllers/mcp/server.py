import logging
import sys
from time import perf_counter
from typing import Any

from mcp.server.mcpserver import MCPServer
from pydantic import ValidationError as PydanticValidationError
from starlette.applications import Starlette

from controllers.mcp.item_controller import library_get
from controllers.mcp.memento_controller import library_get_context, library_publish_context
from controllers.mcp.search_controller import library_search
from controllers.utils.bootstrap.dependencies import build_container
from controllers.utils.infrastructure.observability.context import (
    ensure_request_context,
    reset_request_context,
)
from controllers.utils.infrastructure.observability.logging import log_event
from errors import IdempotencyConflictError, NotFoundError, SearchBackendError
from models.access import SectionRef
from models.experiment_report import ExperimentReport

logger = logging.getLogger(__name__)


def _section(value: object) -> SectionRef | None:
    if value in (None, ""):
        return None
    if isinstance(value, dict):
        return SectionRef.model_validate(value)
    return SectionRef.parse(str(value))


def _mcp_outcome(error: BaseException | None) -> str:
    if error is None:
        return "success"
    if isinstance(error, IdempotencyConflictError):
        return "idempotency_conflict"
    if isinstance(error, SearchBackendError):
        return "gbrain_error"
    if isinstance(error, (KeyError, PydanticValidationError, ValueError)):
        return "validation_error"
    return "internal_error"


async def dispatch(method: str, params: dict[str, Any]) -> dict[str, Any]:
    container = await build_container()
    context_token = ensure_request_context()
    started = perf_counter()
    try:
        if method == "library_search":
            return await library_search(
                container,
                str(params["query"]),
                int(params.get("limit", 10)),
                list(params.get("sections", [])),
            )
        if method == "library_get":
            return await library_get(container, str(params["item_id_or_slug"]))
        if method == "library_get_related":
            item, _slug = await container.items.get(str(params["item_id_or_slug"]))
            related = []
            for relation in item.related:
                try:
                    related_item, related_slug = await container.items.get(relation.target_id)
                except NotFoundError:
                    continue
                related.append(
                    {
                        "relation": relation.type.value,
                        "item": related_item.model_dump(mode="json"),
                        "slug": related_slug,
                    }
                )
            return {"items": related}
        if method == "library_get_context":
            return await library_get_context(
                container,
                query=str(params["query"]),
                project=str(params.get("project", "")),
                repository=str(params.get("repository", "")),
                work_item=(str(params["work_item"]) if params.get("work_item") else None),
                limit=int(params.get("limit", 20)),
            )
        if method == "library_publish_context":
            return await library_publish_context(
                container,
                dict(params["payload"]),
                str(params["idempotency_key"]),
            )
        if method == "library_save_experiment_report":
            payload = dict(params["payload"])
            section = _section(payload.pop("section", None))
            report = ExperimentReport.model_validate(payload)
            result = await container.reports.save(
                report,
                attachment_upload_ids=list(payload.get("artifact_upload_ids", [])),
                idempotency_key=str(params["idempotency_key"]),
                section=section,
            )
            return result.model_dump(mode="json")
        if method == "library_save_idea":
            payload = dict(params["payload"])
            section = _section(payload.pop("section", None))
            result = await container.ideas.save(
                str(payload["title"]),
                str(payload.get("content", "")),
                list(payload.get("tags", [])),
                str(params["idempotency_key"]),
                section=section,
            )
            return result.model_dump(mode="json")
        if method == "library_save_publication":
            payload = dict(params["payload"])
            section = _section(payload.pop("section", None))
            result = await container.publications.save(
                str(payload["title"]),
                str(payload.get("summary", "")),
                str(payload["url"]) if payload.get("url") else None,
                list(payload.get("authors", [])),
                str(params["idempotency_key"]),
                section=section,
            )
            return result.model_dump(mode="json")
        raise ValueError(f"Unknown MCP method: {method}")
    finally:
        error = sys.exc_info()[1]
        outcome = _mcp_outcome(error)
        duration = perf_counter() - started
        container.observability.recorder.record_mcp(
            tool=method,
            outcome=outcome,
            duration_seconds=duration,
        )
        log_event(
            logger,
            "mcp.request.completed",
            tool=method,
            outcome=outcome,
            duration_ms=round(duration * 1000, 3),
            error_code=type(error).__name__ if error is not None else None,
        )
        try:
            await container.close()
        finally:
            reset_request_context(context_token)


async def library_search_tool(
    query: str, limit: int = 10, sections: list[str] | None = None
) -> dict[str, Any]:
    """Search only the library sections allowed to the caller."""
    return await dispatch(
        "library_search", {"query": query, "limit": limit, "sections": sections or []}
    )


async def library_get_tool(item_id_or_slug: str) -> dict[str, Any]:
    """Get one library item by stable ID or slug."""
    return await dispatch("library_get", {"item_id_or_slug": item_id_or_slug})


async def library_get_related_tool(item_id_or_slug: str) -> dict[str, Any]:
    """Get explicitly related library items."""
    return await dispatch("library_get_related", {"item_id_or_slug": item_id_or_slug})


async def library_get_context_tool(
    query: str,
    project: str = "",
    repository: str = "",
    work_item: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Find development history from a free-form task or bug description."""
    return await dispatch(
        "library_get_context",
        {
            "query": query,
            "project": project,
            "repository": repository,
            "work_item": work_item,
            "limit": limit,
        },
    )


async def library_publish_context_tool(
    payload: dict[str, Any], idempotency_key: str
) -> dict[str, Any]:
    """Publish an immutable development decision, checkpoint, problem, or evidence."""
    return await dispatch(
        "library_publish_context",
        {"payload": payload, "idempotency_key": idempotency_key},
    )


async def library_save_experiment_report_tool(
    payload: dict[str, Any], idempotency_key: str
) -> dict[str, Any]:
    """Save a durable final AutoResearch experiment report."""
    return await dispatch(
        "library_save_experiment_report",
        {"payload": payload, "idempotency_key": idempotency_key},
    )


async def library_save_idea_tool(payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
    """Save a research idea."""
    return await dispatch(
        "library_save_idea", {"payload": payload, "idempotency_key": idempotency_key}
    )


async def library_save_publication_tool(
    payload: dict[str, Any], idempotency_key: str
) -> dict[str, Any]:
    """Save publication metadata."""
    return await dispatch(
        "library_save_publication",
        {"payload": payload, "idempotency_key": idempotency_key},
    )


def create_mcp_server() -> MCPServer[Any]:
    server = MCPServer("Research Library")
    server.add_tool(library_search_tool, name="library_search")
    server.add_tool(library_get_tool, name="library_get")
    server.add_tool(library_get_related_tool, name="library_get_related")
    server.add_tool(library_get_context_tool, name="library_get_context")
    server.add_tool(library_publish_context_tool, name="library_publish_context")
    server.add_tool(
        library_save_experiment_report_tool,
        name="library_save_experiment_report",
    )
    server.add_tool(library_save_idea_tool, name="library_save_idea")
    server.add_tool(library_save_publication_tool, name="library_save_publication")
    return server


def create_mcp_http_app() -> tuple[MCPServer[Any], Starlette]:
    server = create_mcp_server()
    http_app = server.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        host="0.0.0.0",
    )
    return server, http_app


mcp = create_mcp_server()


if __name__ == "__main__":
    mcp.run()
