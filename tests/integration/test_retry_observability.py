from pathlib import Path

import pytest

from controllers.utils.bootstrap.dependencies import build_container
from controllers.utils.bootstrap.settings import Settings
from controllers.utils.infrastructure.observability.bootstrap import shutdown_observability
from controllers.workers.retry_controller import RetryWorker
from models.access import SectionRef
from models.commands import CreateItemCommand
from models.enums import LibraryItemType
from tests.fakes import FakeGBrainAdapter


@pytest.mark.asyncio
async def test_retry_worker_updates_outcome_and_pending_gauges(tmp_path: Path) -> None:
    container = await build_container(
        Settings(
            _env_file=None,
            library_data_root=tmp_path / "library",
            metrics_endpoint_enabled=True,
            metrics_auth_token="metrics-secret",
            otel_deployment_environment="test",
        ),
        gbrain_factory=FakeGBrainAdapter,
    )
    try:
        saved = await container.items.create(
            CreateItemCommand(type=LibraryItemType.NOTE, title="Retry metric target")
        )
        section = await container.sections_store.require(SectionRef.parse("research/main"))
        await container.items.jobs.create_pending_index(
            saved.item_id, "temporary", section.id
        )

        assert await RetryWorker(container).process_once() == 1

        rendered = container.observability.render_metrics().decode("utf-8")
        assert "library_retry_jobs_total" in rendered
        assert 'outcome="completed"' in rendered
        assert "library_pending_index_jobs" in rendered
        assert "} 0.0" in rendered
        assert "temporary" not in rendered
        assert saved.item_id not in rendered
    finally:
        await container.close()
        shutdown_observability()
