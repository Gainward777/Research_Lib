from pathlib import Path

import pytest

from controllers.utils.BD.collections import CollectionStore
from controllers.utils.bootstrap.dependencies import build_container
from controllers.utils.bootstrap.settings import Settings
from tests.fakes import FakeGBrainAdapter


@pytest.mark.asyncio
async def test_collection_survives_database_round_trip(tmp_path: Path) -> None:
    settings = Settings(library_data_root=tmp_path / "library")
    container = await build_container(settings, gbrain_factory=FakeGBrainAdapter)
    try:
        store = CollectionStore(container.database)
        await store.start(123)
        assert await store.add(123, "first") == 1
        assert await store.add(123, "second") == 2
        assert await store.pop(123) == ["first", "second"]
        assert not await store.is_active(123)
    finally:
        await container.close()


@pytest.mark.asyncio
async def test_collection_keeps_attachment_upload_ids(tmp_path: Path) -> None:
    settings = Settings(library_data_root=tmp_path / "library")
    container = await build_container(settings, gbrain_factory=FakeGBrainAdapter)
    try:
        store = CollectionStore(container.database)
        await store.start(456)
        assert await store.add(456, "report caption", ["upload_1", "upload_2"]) == 2
        material = await store.pop_material(456)
        assert material.text_parts == ["report caption"]
        assert material.upload_ids == ["upload_1", "upload_2"]
    finally:
        await container.close()


@pytest.mark.asyncio
async def test_bootstrap_installs_research_schema(tmp_path: Path) -> None:
    settings = Settings(library_data_root=tmp_path / "library")
    container = await build_container(settings, gbrain_factory=FakeGBrainAdapter)
    try:
        schema = settings.library_brain_root / "_system" / "schemas" / "research-v1" / "schema.yaml"
        assert schema.exists()
        assert "experiment-report" in schema.read_text(encoding="utf-8")
    finally:
        await container.close()
