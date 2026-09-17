from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from controllers.utils.infrastructure.gbrain.adapter import GBrainAdapter
from errors import SearchBackendError
from models.commands import SearchCommand
from models.enums import LibraryItemType
from models.library_item import LibraryItem


def test_gbrain_result_normalization() -> None:
    hits = GBrainAdapter._normalize_hits(
        {
            "data": {
                "results": [
                    {
                        "slug": "ideas/example",
                        "frontmatter": {
                            "id": "lib_example",
                            "type": "idea",
                            "title": "Example",
                            "tags": ["test"],
                        },
                        "snippet": "Relevant text",
                        "score": 0.75,
                    }
                ]
            }
        },
        10,
    )

    assert hits[0].item_id == "lib_example"
    assert hits[0].slug == "ideas/example"
    assert hits[0].score == 0.75


def test_gbrain_environment_allowlist_is_explicit() -> None:
    assert "OPENAI_API_KEY" in GBrainAdapter.SAFE_ENVIRONMENT_NAMES
    assert "ANTHROPIC_API_KEY" not in GBrainAdapter.SAFE_ENVIRONMENT_NAMES
    assert "ZEROENTROPY_API_KEY" not in GBrainAdapter.SAFE_ENVIRONMENT_NAMES
    assert "VOYAGE_API_KEY" not in GBrainAdapter.SAFE_ENVIRONMENT_NAMES
    assert "LIBRARY_API_TOKEN" not in GBrainAdapter.SAFE_ENVIRONMENT_NAMES
    assert "MCP_AUTH_TOKEN" not in GBrainAdapter.SAFE_ENVIRONMENT_NAMES
    assert "TELEGRAM_BOT_TOKEN" not in GBrainAdapter.SAFE_ENVIRONMENT_NAMES


@pytest.mark.asyncio
async def test_initialize_creates_real_pglite_brain(tmp_path: Path) -> None:
    adapter = GBrainAdapter(
        SimpleNamespace(),
        home=tmp_path / "gbrain",
        expected_version="0.45.12.0",
    )
    adapter._verify_version = AsyncMock()
    adapter._run_json = AsyncMock(return_value={"status": "success"})
    adapter._doctor_health = AsyncMock(return_value=True)

    assert await adapter.initialize() is True

    arguments = adapter._run_json.await_args.args[0]
    assert arguments[:3] == ["init", "--pglite", "--non-interactive"]
    assert "--no-embedding" in arguments
    assert str(tmp_path / "gbrain" / "brain.pglite") in arguments


@pytest.mark.asyncio
async def test_version_mismatch_is_fatal(tmp_path: Path) -> None:
    adapter = GBrainAdapter(
        SimpleNamespace(),
        home=tmp_path,
        expected_version="0.45.12.0",
    )
    adapter._run_command = AsyncMock(return_value=b"gbrain 0.45.11.0\n")

    with pytest.raises(SearchBackendError, match="version mismatch"):
        await adapter._verify_version()


@pytest.mark.asyncio
async def test_search_keeps_application_filters_out_of_gbrain_payload(tmp_path: Path) -> None:
    adapter = GBrainAdapter(SimpleNamespace(), home=tmp_path)
    adapter._run_call = AsyncMock(
        return_value=[
            {
                "slug": "ideas/match",
                "frontmatter": {
                    "id": "lib_match",
                    "type": "idea",
                    "title": "Match",
                    "tags": ["research"],
                },
            },
            {
                "slug": "inbox/skip",
                "frontmatter": {
                    "id": "lib_skip",
                    "type": "note",
                    "title": "Skip",
                    "tags": [],
                },
            },
        ]
    )

    hits = await adapter.search(
        SearchCommand(
            query="marker",
            types=[LibraryItemType.IDEA],
            tags=["research"],
            limit=5,
        )
    )

    assert [hit.item_id for hit in hits] == ["lib_match"]
    assert adapter._run_call.await_args.args == ("search", {"query": "marker", "limit": 100})


@pytest.mark.asyncio
async def test_health_only_blocks_on_storage_checks(tmp_path: Path) -> None:
    adapter = GBrainAdapter(SimpleNamespace(), home=tmp_path)
    adapter._run_json = AsyncMock(
        return_value={
            "status": "unhealthy",
            "checks": [
                {"name": "connection", "status": "ok"},
                {"name": "brain_score", "status": "fail"},
            ],
        }
    )

    assert await adapter._doctor_health() is True
    assert adapter._run_json.await_args.args[0] == ["doctor", "--json"]


@pytest.mark.asyncio
async def test_health_rejects_failed_gbrain_connection(tmp_path: Path) -> None:
    adapter = GBrainAdapter(SimpleNamespace(), home=tmp_path)
    adapter._run_json = AsyncMock(
        return_value={
            "status": "unhealthy",
            "checks": [{"name": "connection", "status": "fail"}],
        }
    )

    assert await adapter._doctor_health() is False


@pytest.mark.asyncio
async def test_readiness_opens_gbrain_stats(tmp_path: Path) -> None:
    adapter = GBrainAdapter(SimpleNamespace(), home=tmp_path)
    adapter._run_call = AsyncMock(return_value={"page_count": 0})

    assert await adapter.health() is True
    assert adapter._run_call.await_args.args == ("get_stats", {})


@pytest.mark.asyncio
async def test_think_returns_synthesized_answer_with_library_sources(tmp_path: Path) -> None:
    item = LibraryItem(
        type=LibraryItemType.IDEA,
        title="Example",
        summary="Relevant material",
    )
    repository = SimpleNamespace(get=AsyncMock(return_value=(item, "ideas/example")))
    adapter = GBrainAdapter(repository, home=tmp_path, think_model="openai:gpt-4.1-mini")
    adapter._run_call = AsyncMock(
        return_value={
            "answer": "  Ответ GBrain.\nВторая строка.  ",
            "synthesisOk": True,
            "citations": [{"page_slug": "ideas/example", "row_num": None}],
        }
    )
    question = "Что известно?"

    result = await adapter.think(SearchCommand(query=question))

    assert result.answer == "  Ответ GBrain.\nВторая строка.  "
    assert [source.item_id for source in result.sources] == [item.id]
    assert adapter._run_call.await_args.args == (
        "think",
        {"question": question, "model": "openai:gpt-4.1-mini"},
    )
