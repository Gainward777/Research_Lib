from pathlib import Path

import pytest

from controllers.utils.bootstrap.dependencies import build_container
from controllers.utils.bootstrap.settings import Settings
from controllers.utils.infrastructure.observability.bootstrap import shutdown_observability
from models.enums import RelationType
from models.memento import DevelopmentContextQuery, PublishDevelopmentContext
from tests.fakes import FakeGBrainAdapter


@pytest.mark.asyncio
async def test_consulted_context_is_durable_idempotent_and_measured(
    tmp_path: Path,
) -> None:
    container = await build_container(
        Settings(
            _env_file=None,
            library_data_root=tmp_path / "library",
            metrics_endpoint_enabled=True,
            metrics_auth_token="metrics-secret",
            metrics_allowed_projects=["platform"],
            otel_deployment_environment="test",
        ),
        gbrain_factory=FakeGBrainAdapter,
    )
    try:
        source = await container.memento.publish(
            PublishDevelopmentContext(
                context_kind="implementation_snapshot",
                project="platform",
                repository="backend-api",
                work_item="AUTH-142",
                title="Token implementation",
                content="Refresh tokens are encrypted before persistence.",
            ),
            idempotency_key="memento:AUTH-142:snapshot:source",
        )
        publication = PublishDevelopmentContext(
            context_kind="decision",
            project="platform",
            repository="backend-api",
            work_item="BUG-731",
            title="Keep encrypted refresh tokens",
            content="The bug fix preserves encrypted token persistence.",
            consulted_context_item_ids=[source.item_id, source.item_id],
        )
        saved = await container.memento.publish(
            publication,
            idempotency_key="memento:BUG-731:decision:1",
        )
        duplicate = await container.memento.publish(
            publication,
            idempotency_key="memento:BUG-731:decision:1",
        )
        bundle = await container.memento.get_context(
            DevelopmentContextQuery(
                query="encrypted token persistence",
                project="platform",
                repository="backend-api",
            )
        )

        stored, _slug = await container.items.get(saved.item_id)
        source_relations = [
            relation for relation in stored.related if relation.type == RelationType.HAS_SOURCE
        ]
        assert duplicate.item_id == saved.item_id
        assert duplicate.created is True
        assert stored.metadata["consulted_context_item_ids"] == [source.item_id]
        assert [(relation.type, relation.target_id) for relation in source_relations] == [
            (RelationType.HAS_SOURCE, source.item_id)
        ]
        assert bundle.decisions[0].consulted_context_item_ids == [source.item_id]

        rendered = container.observability.render_metrics().decode("utf-8")
        assert 'outcome="created"' in rendered
        assert 'outcome="deduplicated"' in rendered
        assert 'outcome="found"' in rendered
        assert 'project="platform"' in rendered
        assert source.item_id not in rendered
    finally:
        await container.close()
        shutdown_observability()


@pytest.mark.asyncio
async def test_inferred_memento_project_is_used_as_metric_label(tmp_path: Path) -> None:
    container = await build_container(
        Settings(
            _env_file=None,
            library_data_root=tmp_path / "library",
            metrics_endpoint_enabled=True,
            metrics_auth_token="metrics-secret",
            metrics_allowed_projects=["_unassigned"],
            otel_deployment_environment="test",
        ),
        gbrain_factory=FakeGBrainAdapter,
    )
    try:
        await container.memento.publish(
            PublishDevelopmentContext(
                context_kind="checkpoint",
                work_item="OPS-17",
                title="Inferred metric scope",
                content="The observable service resolves the project before recording.",
            ),
            idempotency_key="memento:OPS-17:checkpoint:1",
        )

        rendered = container.observability.render_metrics().decode("utf-8")
        assert 'project="_unassigned"' in rendered
        assert 'project="_unknown"' not in rendered
    finally:
        await container.close()
        shutdown_observability()
