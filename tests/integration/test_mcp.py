from pathlib import Path

import pytest

from controllers.mcp.server import dispatch, mcp


@pytest.mark.asyncio
async def test_mcp_tools_and_round_trip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LIBRARY_DATA_ROOT", str(tmp_path / "library"))
    monkeypatch.setenv("LIBRARY_GBRAIN_MODE", "local")

    tools = await mcp.list_tools()
    assert {tool.name for tool in tools} == {
        "library_search",
        "library_get",
        "library_get_related",
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
