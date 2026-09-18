import io
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from controllers.utils.bootstrap.settings import Settings
from controllers.utils.infrastructure.gbrain.observable_adapter import (
    ObservableGBrainAdapter,
)
from controllers.utils.infrastructure.observability.context import bind_request_context
from controllers.utils.infrastructure.observability.logging import JsonFormatter, log_event
from controllers.utils.infrastructure.observability.metrics import (
    CompositeMetricsRecorder,
    PrometheusMetricsRecorder,
)
from errors import SearchBackendError
from models.access import SectionRef
from models.commands import SearchCommand

TEST_SECTION = SectionRef.parse("research/main")


def test_prometheus_metrics_use_bounded_labels_and_hide_content() -> None:
    recorder = PrometheusMetricsRecorder(
        service="research-library",
        environment="test",
        allowed_projects=["platform"],
    )
    recorder.record_memento_search(
        outcome="found",
        project="user supplied project",
        duration_seconds=0.25,
        hit_count=2,
        block_counts={"decisions": 1, "untrusted block": 1},
    )
    recorder.record_memento_publish(
        kind="decision",
        outcome="created",
        project="platform",
        duration_seconds=0.5,
        supersedes=True,
        consulted_sources=2,
    )
    recorder.set_readiness(ready=False)

    rendered = recorder.render().decode("utf-8")

    assert "memento_context_search_requests_total" in rendered
    assert 'project="_unknown"' in rendered
    assert 'block="_unknown"' in rendered
    assert 'project="platform"' in rendered
    assert "user supplied project" not in rendered
    assert "query" not in rendered
    assert "content" not in rendered
    assert 'library_readiness{environment="test",service="research-library"} 0.0' in rendered
    assert (
        'library_observability_heartbeat{environment="test",service="research-library"} 1.0'
        in rendered
    )


def test_access_metrics_use_bounded_labels_without_principal_ids() -> None:
    recorder = PrometheusMetricsRecorder(
        service="research-library",
        environment="test",
        allowed_projects=[],
    )
    recorder.record_auth(surface="api", outcome="success", legacy=False)
    recorder.record_auth_denial(operation="publish", domain="memento")
    recorder.record_section_read(policy="restricted")
    recorder.set_token_counts(active=2, revoked=1, expired=3)

    rendered = recorder.render().decode("utf-8")

    assert "library_auth_requests_total" in rendered
    assert 'surface="api"' in rendered
    assert 'legacy="false"' in rendered
    assert "library_auth_denials_total" in rendered
    assert 'operation="publish"' in rendered
    assert 'domain="memento"' in rendered
    assert "library_section_reads_total" in rendered
    assert 'policy="restricted"' in rendered
    assert "library_access_tokens" in rendered
    assert 'status="active"' in rendered
    assert 'status="revoked"' in rendered
    assert 'status="expired"' in rendered
    assert 'principal_id="' not in rendered
    assert 'principal="' not in rendered

def test_json_log_has_request_context_without_sensitive_fields() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter(service="research-library", environment="test"))
    test_logger = logging.getLogger("tests.observability.safe-log")
    original_handlers = test_logger.handlers[:]
    original_propagate = test_logger.propagate
    original_level = test_logger.level
    test_logger.handlers = [handler]
    test_logger.propagate = False
    test_logger.setLevel(logging.INFO)
    try:
        with bind_request_context(
            request_id="req_test",
            principal_id="principal_safe",
            project="platform",
        ):
            log_event(
                test_logger,
                "memento.context.search.completed",
                outcome="found",
                item_id="lib_safe",
                query="sensitive query",
                content="sensitive content",
                authorization="Bearer secret",
            )
    finally:
        test_logger.handlers = original_handlers
        test_logger.propagate = original_propagate
        test_logger.setLevel(original_level)

    payload = json.loads(stream.getvalue())
    assert payload["request_id"] == "req_test"
    assert payload["principal_id"] == "principal_safe"
    assert payload["service"] == "research-library"
    assert payload["environment"] == "test"
    assert payload["item_id"] == "lib_safe"
    assert "query" not in payload
    assert "content" not in payload
    assert "authorization" not in payload
    assert "secret" not in stream.getvalue()


def test_metrics_configuration_requires_separate_secrets() -> None:
    with pytest.raises(ValidationError, match="METRICS_AUTH_TOKEN"):
        Settings(_env_file=None, metrics_endpoint_enabled=True)

    with pytest.raises(ValidationError, match="OTEL_METRICS_EXPORTER=otlp"):
        Settings(_env_file=None, metrics_enabled=True)

    with pytest.raises(ValidationError, match="must differ"):
        Settings(
            _env_file=None,
            library_api_token="shared-secret",
            metrics_auth_token="shared-secret",
        )

    with pytest.raises(ValidationError, match="must differ"):
        Settings(
            _env_file=None,
            library_telegram_access_token="shared-secret",
            metrics_auth_token="shared-secret",
        )


@pytest.mark.asyncio
async def test_gbrain_search_records_outcome_and_latency(tmp_path: Path) -> None:
    recorder = PrometheusMetricsRecorder(
        service="research-library",
        environment="test",
        allowed_projects=[],
    )
    adapter = ObservableGBrainAdapter(
        SimpleNamespace(),
        home=tmp_path,
        metrics=recorder,
    )
    adapter._ensure_source = AsyncMock()
    adapter._run_call = AsyncMock(return_value=[])

    assert await adapter.search(
        SearchCommand(query="safe test query", sections=[TEST_SECTION])
    ) == []

    rendered = recorder.render().decode("utf-8")
    assert "gbrain_operation_requests_total" in rendered
    assert 'operation="search"' in rendered
    assert 'outcome="success"' in rendered
    assert "safe test query" not in rendered


@pytest.mark.asyncio
async def test_gbrain_timeout_is_measured_without_query_content(tmp_path: Path) -> None:
    recorder = PrometheusMetricsRecorder(
        service="research-library",
        environment="test",
        allowed_projects=[],
    )
    adapter = ObservableGBrainAdapter(
        SimpleNamespace(),
        home=tmp_path,
        metrics=recorder,
    )
    adapter._ensure_source = AsyncMock()
    adapter._run_call = AsyncMock(
        side_effect=SearchBackendError("GBrain command timed out after 1 second")
    )

    with pytest.raises(SearchBackendError, match="timed out"):
        await adapter.search(
            SearchCommand(query="private timeout query", sections=[TEST_SECTION])
        )

    rendered = recorder.render().decode("utf-8")
    assert 'outcome="timeout"' in rendered
    assert "private timeout query" not in rendered


def test_broken_metrics_backend_never_breaks_application_work() -> None:
    class BrokenRecorder:
        def record_gbrain(self, **_values: object) -> None:
            raise RuntimeError("backend unavailable")

        def shutdown(self) -> None:
            raise RuntimeError("backend unavailable")

    recorder = CompositeMetricsRecorder([BrokenRecorder()])

    recorder.record_gbrain(
        operation="search",
        outcome="success",
        duration_seconds=0.1,
    )
    recorder.shutdown()
