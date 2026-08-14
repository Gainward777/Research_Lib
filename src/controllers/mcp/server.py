from typing import Any

from mcp.server.mcpserver import MCPServer
from starlette.applications import Starlette

from controllers.mcp.item_controller import library_get
from controllers.mcp.search_controller import library_search
from controllers.utils.bootstrap.dependencies import build_container
from models.experiment_report import ExperimentReport


async def dispatch(method: str, params: dict[str, Any]) -> dict[str, Any]:
    container = await build_container()
    try:
        if method == "library_search":
            return await library_search(
                container, str(params["query"]), int(params.get("limit", 10))
            )
        if method == "library_get":
            return await library_get(container, str(params["item_id_or_slug"]))
        if method == "library_get_related":
            item, _slug = await container.items.get(str(params["item_id_or_slug"]))
            related = []
            for relation in item.related:
                related_item, related_slug = await container.items.get(relation.target_id)
                related.append(
                    {
                        "relation": relation.type.value,
                        "item": related_item.model_dump(mode="json"),
                        "slug": related_slug,
                    }
                )
            return {"items": related}
        if method == "library_save_experiment_report":
            payload = dict(params["payload"])
            report = ExperimentReport.model_validate(payload)
            result = await container.reports.save(
                report,
                attachment_upload_ids=list(payload.get("artifact_upload_ids", [])),
                idempotency_key=str(params["idempotency_key"]),
            )
            return result.model_dump(mode="json")
        if method == "library_save_idea":
            payload = dict(params["payload"])
            result = await container.ideas.save(
                str(payload["title"]),
                str(payload.get("content", "")),
                list(payload.get("tags", [])),
                str(params["idempotency_key"]),
            )
            return result.model_dump(mode="json")
        if method == "library_save_publication":
            payload = dict(params["payload"])
            result = await container.publications.save(
                str(payload["title"]),
                str(payload.get("summary", "")),
                str(payload["url"]) if payload.get("url") else None,
                list(payload.get("authors", [])),
                str(params["idempotency_key"]),
            )
            return result.model_dump(mode="json")
        raise ValueError(f"Unknown MCP method: {method}")
    finally:
        await container.close()


async def library_search_tool(query: str, limit: int = 10) -> dict[str, Any]:
    """Search the research library without LLM synthesis."""
    return await dispatch("library_search", {"query": query, "limit": limit})


async def library_get_tool(item_id_or_slug: str) -> dict[str, Any]:
    """Get one library item by stable ID or slug."""
    return await dispatch("library_get", {"item_id_or_slug": item_id_or_slug})


async def library_get_related_tool(item_id_or_slug: str) -> dict[str, Any]:
    """Get explicitly related library items."""
    return await dispatch("library_get_related", {"item_id_or_slug": item_id_or_slug})


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
