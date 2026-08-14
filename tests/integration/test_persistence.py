from pathlib import Path

import pytest

from controllers.utils.bootstrap.dependencies import build_container
from controllers.utils.bootstrap.settings import Settings
from models.commands import CreateItemCommand, SearchCommand
from models.enums import LibraryItemType


@pytest.mark.asyncio
async def test_write_restart_search(tmp_path: Path) -> None:
    settings = Settings(library_data_root=tmp_path / "library", library_gbrain_mode="local")
    first = await build_container(settings)
    result = await first.items.create(
        CreateItemCommand(
            type=LibraryItemType.NOTE,
            title="Persistent result",
            content="A unique restart-search-marker survives restart.",
        ),
        idempotency_key="persistence:1",
    )
    await first.close()

    second = await build_container(settings)
    try:
        hits = await second.search.search(SearchCommand(query="restart-search-marker"))
        assert hits[0].item_id == result.item_id
    finally:
        await second.close()
