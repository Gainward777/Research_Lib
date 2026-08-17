from pathlib import Path

import pytest

from controllers.utils.bootstrap.dependencies import build_container
from controllers.utils.bootstrap.settings import Settings
from controllers.workers.retry_controller import RetryWorker
from models.commands import CreateItemCommand
from models.enums import LibraryItemType
from tests.fakes import FakeGBrainAdapter


@pytest.mark.asyncio
async def test_pending_index_job_is_completed(tmp_path: Path) -> None:
    container = await build_container(
        Settings(library_data_root=tmp_path / "library"),
        gbrain_factory=FakeGBrainAdapter,
    )
    try:
        saved = await container.items.create(
            CreateItemCommand(type=LibraryItemType.NOTE, title="Retry target")
        )
        job_id = await container.items.jobs.create_pending_index(saved.item_id, "temporary")

        assert await RetryWorker(container).process_once() == 1

        job = await container.jobs.get(job_id)
        assert job["status"] == "completed"
        assert job["attempts"] == 1
    finally:
        await container.close()
