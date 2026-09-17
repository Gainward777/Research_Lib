from pathlib import Path

import pytest

from controllers.mcp.server import dispatch, mcp
from controllers.utils.bootstrap.dependencies import build_container
from tests.fakes import FakeGBrainAdapter

INITIALIZE_REQUEST = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "integration-test", "version": "1"},
    },
}


def test_streamable_http_endpoint_and_auth(client) -> None:
    headers = {"Accept": "application/json, text/event-stream"}
    assert client.post("/mcp", json=INITIALIZE_REQUEST, headers=headers).status_code == 401

    headers["Authorization"] = "Bearer test-mcp-token"
    response = client.post("/mcp", json=INITIALIZE_REQUEST, headers=headers)

    assert response.status_code == 200
    assert response.json()["result"]["serverInfo"]["name"] == "Research Library"

    headers["MCP-Protocol-Version"] = "2025-06-18"
    tools_response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        headers=headers,
    )
    assert tools_response.status_code == 200
    assert {tool["name"] for tool in tools_response.json()["result"]["tools"]} == {
        "library_search",
        "library_get",
        "library_get_related",
        "library_get_context",
        "library_publish_context",
        "library_save_experiment_report",
        "library_save_idea",
        "library_save_publication",
    }


@pytest.mark.asyncio
async def test_mcp_tools_and_round_trip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LIBRARY_DATA_ROOT", str(tmp_path / "library"))

    async def build_test_container():
        return await build_container(gbrain_factory=FakeGBrainAdapter)

    monkeypatch.setattr("controllers.mcp.server.build_container", build_test_container)

    tools = await mcp.list_tools()
    assert {tool.name for tool in tools} == {
        "library_search",
        "library_get",
        "library_get_related",
        "library_get_context",
        "library_publish_context",
        "library_save_experiment_report",
        "library_save_idea",
        "library_save_publication",
    }

    saved = await dispatch(
        "library_save_idea",
        {
            "payload": {
                "title": "MCP idea",
                "content": "A durable MCP marker.",
                "tags": ["mcp"],
            },
            "idempotency_key": "mcp:idea:1",
        },
    )
    found = await dispatch("library_search", {"query": "durable MCP marker", "limit": 5})

    assert found["hits"][0]["item_id"] == saved["item_id"]

    context = await dispatch(
        "library_publish_context",
        {
            "payload": {
                "context_kind": "problem",
                "project": "platform",
                "repository": "backend-api",
                "work_item": "BUG-731",
                "title": "Unexpected logout",
                "content": "Users are logged out after refresh token expiration.",
                "commit": "d91f203",
                "paths": ["src/auth/oauth.py"],
            },
            "idempotency_key": "memento:BUG-731:problem:1",
        },
    )
    context_bundle = await dispatch(
        "library_get_context",
        {
            "query": "logged out refresh token",
            "project": "platform",
            "repository": "backend-api",
        },
    )

    assert context_bundle["known_problems"][0]["item_id"] == context["item_id"]
    assert context_bundle["known_problems"][0]["work_item"] == "BUG-731"
