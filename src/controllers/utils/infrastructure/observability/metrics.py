from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from opentelemetry.sdk.metrics import MeterProvider
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

MEMENTO_KINDS = {
    "decision",
    "checkpoint",
    "implementation_snapshot",
    "problem",
    "test_evidence",
}
MEMENTO_BLOCKS = {
    "related_implementations",
    "decisions",
    "known_problems",
    "tests_and_evidence",
    "checkpoints",
}
GBRAIN_OPERATIONS = {"search", "get", "put", "think", "health", "reindex"}
MCP_TOOLS = {
    "library_search",
    "library_get",
    "library_get_related",
    "library_get_context",
    "library_publish_context",
    "library_save_experiment_report",
    "library_save_idea",
    "library_save_publication",
}


class MetricsRecorder(Protocol):
    def record_memento_search(
        self,
        *,
        outcome: str,
        project: str,
        duration_seconds: float,
        hit_count: int,
        block_counts: dict[str, int],
    ) -> None: ...

    def record_memento_publish(
        self,
        *,
        kind: str,
        outcome: str,
        project: str,
        duration_seconds: float,
        supersedes: bool,
        consulted_sources: int,
    ) -> None: ...

    def record_gbrain(self, *, operation: str, outcome: str, duration_seconds: float) -> None: ...

    def set_pending_index(self, *, jobs: int, oldest_age_seconds: float) -> None: ...

    def record_retry(self, *, outcome: str) -> None: ...

    def record_mcp(self, *, tool: str, outcome: str, duration_seconds: float) -> None: ...

    def record_mcp_auth_failure(self, *, reason: str) -> None: ...

    def record_auth(self, *, surface: str, outcome: str, legacy: bool) -> None: ...

    def record_auth_denial(self, *, operation: str, domain: str) -> None: ...

    def record_section_read(self, *, policy: str) -> None: ...

    def set_token_counts(self, *, active: int, revoked: int, expired: int) -> None: ...

    def set_readiness(self, *, ready: bool) -> None: ...

    def shutdown(self) -> None: ...


class LabelNormalizer:
    def __init__(self, allowed_projects: Iterable[str]) -> None:
        self.allowed_projects = {
            value.strip().casefold() for value in allowed_projects if value.strip()
        }

    def project(self, value: str) -> str:
        normalized = value.strip().casefold()
        return normalized if normalized in self.allowed_projects else "_unknown"

    @staticmethod
    def fixed(value: str, allowed: set[str]) -> str:
        return value if value in allowed else "_unknown"


class NoOpMetricsRecorder:
    def record_memento_search(self, **_values: object) -> None:
        return None

    def record_memento_publish(self, **_values: object) -> None:
        return None

    def record_gbrain(self, **_values: object) -> None:
        return None

    def set_pending_index(self, **_values: object) -> None:
        return None

    def record_retry(self, **_values: object) -> None:
        return None

    def record_mcp(self, **_values: object) -> None:
        return None

    def record_mcp_auth_failure(self, **_values: object) -> None:
        return None

    def record_auth(self, **_values: object) -> None:
        return None

    def record_auth_denial(self, **_values: object) -> None:
        return None

    def record_section_read(self, **_values: object) -> None:
        return None

    def set_token_counts(self, **_values: object) -> None:
        return None

    def set_readiness(self, **_values: object) -> None:
        return None

    def shutdown(self) -> None:
        return None


class PrometheusMetricsRecorder:
    content_type = "text/plain; version=0.0.4; charset=utf-8"

    def __init__(
        self,
        *,
        service: str,
        environment: str,
        allowed_projects: Iterable[str],
    ) -> None:
        self.registry = CollectorRegistry(auto_describe=True)
        self.normalizer = LabelNormalizer(allowed_projects)
        self.base = {"service": service, "environment": environment}
        base_labels = ["service", "environment"]

        self.search_requests = Counter(
            "memento_context_search_requests_total",
            "Memento context searches.",
            [*base_labels, "outcome", "project"],
            registry=self.registry,
        )
        self.search_duration = Histogram(
            "memento_context_search_duration_seconds",
            "Memento context search duration.",
            [*base_labels, "outcome", "project"],
            registry=self.registry,
        )
        self.search_hits = Histogram(
            "memento_context_search_hits",
            "Number of hits returned by a Memento context search.",
            [*base_labels, "project"],
            buckets=(0, 1, 2, 3, 5, 10, 20, 50, 100),
            registry=self.registry,
        )
        self.search_blocks = Histogram(
            "memento_context_search_blocks",
            "Number of entries returned in one Memento block.",
            [*base_labels, "block", "project"],
            buckets=(0, 1, 2, 3, 5, 10, 20, 50, 100),
            registry=self.registry,
        )
        self.publish_requests = Counter(
            "memento_context_publish_requests_total",
            "Memento context publications.",
            [*base_labels, "kind", "outcome", "project"],
            registry=self.registry,
        )
        self.publish_duration = Histogram(
            "memento_context_publish_duration_seconds",
            "Memento context publication duration.",
            [*base_labels, "kind", "outcome", "project"],
            registry=self.registry,
        )
        self.supersedes = Counter(
            "memento_context_supersedes_total",
            "Memento publications that supersede an older item.",
            [*base_labels, "kind", "project"],
            registry=self.registry,
        )
        self.consulted_sources = Histogram(
            "memento_context_consulted_sources",
            "Number of durable context sources consulted by a publication.",
            [*base_labels, "kind", "project"],
            buckets=(0, 1, 2, 3, 5, 10, 20, 50),
            registry=self.registry,
        )
        self.gbrain_requests = Counter(
            "gbrain_operation_requests_total",
            "GBrain operations.",
            [*base_labels, "operation", "outcome"],
            registry=self.registry,
        )
        self.gbrain_duration = Histogram(
            "gbrain_operation_duration_seconds",
            "GBrain operation duration.",
            [*base_labels, "operation", "outcome"],
            registry=self.registry,
        )
        self.pending_jobs = Gauge(
            "library_pending_index_jobs",
            "Current number of pending or retryable index jobs.",
            base_labels,
            registry=self.registry,
        )
        self.oldest_pending_age = Gauge(
            "library_oldest_pending_index_age_seconds",
            "Age of the oldest pending index job.",
            base_labels,
            registry=self.registry,
        )
        self.retry_jobs = Counter(
            "library_retry_jobs_total",
            "Index retry outcomes.",
            [*base_labels, "outcome"],
            registry=self.registry,
        )
        self.mcp_requests = Counter(
            "mcp_requests_total",
            "MCP tool requests.",
            [*base_labels, "tool", "outcome"],
            registry=self.registry,
        )
        self.mcp_duration = Histogram(
            "mcp_request_duration_seconds",
            "MCP tool request duration.",
            [*base_labels, "tool", "outcome"],
            registry=self.registry,
        )
        self.mcp_auth_failures = Counter(
            "mcp_auth_failures_total",
            "MCP authentication failures.",
            [*base_labels, "reason"],
            registry=self.registry,
        )
        self.auth_requests = Counter(
            "library_auth_requests_total",
            "Library authentication outcomes.",
            [*base_labels, "surface", "outcome", "legacy"],
            registry=self.registry,
        )
        self.auth_denials = Counter(
            "library_auth_denials_total",
            "Authorization denials without principal labels.",
            [*base_labels, "operation", "domain"],
            registry=self.registry,
        )
        self.section_reads = Counter(
            "library_section_reads_total",
            "Read checks by section policy.",
            [*base_labels, "policy"],
            registry=self.registry,
        )
        self.token_counts = Gauge(
            "library_access_tokens",
            "Access token counts by status.",
            [*base_labels, "status"],
            registry=self.registry,
        )
        self.readiness = Gauge(
            "library_readiness",
            "Whether the application readiness checks currently pass.",
            base_labels,
            registry=self.registry,
        )
        self.heartbeat = Gauge(
            "library_observability_heartbeat",
            "Presence signal exported periodically by the application.",
            base_labels,
            registry=self.registry,
        )
        self.heartbeat.labels(**self.base).set(1)

    def _labels(self, **values: str) -> dict[str, str]:
        return {**self.base, **values}

    def record_memento_search(
        self,
        *,
        outcome: str,
        project: str,
        duration_seconds: float,
        hit_count: int,
        block_counts: dict[str, int],
    ) -> None:
        project = self.normalizer.project(project)
        labels = self._labels(outcome=outcome, project=project)
        self.search_requests.labels(**labels).inc()
        self.search_duration.labels(**labels).observe(duration_seconds)
        self.search_hits.labels(**self._labels(project=project)).observe(hit_count)
        for block, count in block_counts.items():
            block = self.normalizer.fixed(block, MEMENTO_BLOCKS)
            self.search_blocks.labels(**self._labels(block=block, project=project)).observe(count)

    def record_memento_publish(
        self,
        *,
        kind: str,
        outcome: str,
        project: str,
        duration_seconds: float,
        supersedes: bool,
        consulted_sources: int,
    ) -> None:
        kind = self.normalizer.fixed(kind, MEMENTO_KINDS)
        project = self.normalizer.project(project)
        labels = self._labels(kind=kind, outcome=outcome, project=project)
        self.publish_requests.labels(**labels).inc()
        self.publish_duration.labels(**labels).observe(duration_seconds)
        if supersedes:
            self.supersedes.labels(**self._labels(kind=kind, project=project)).inc()
        self.consulted_sources.labels(**self._labels(kind=kind, project=project)).observe(
            consulted_sources
        )

    def record_gbrain(self, *, operation: str, outcome: str, duration_seconds: float) -> None:
        operation = self.normalizer.fixed(operation, GBRAIN_OPERATIONS)
        labels = self._labels(operation=operation, outcome=outcome)
        self.gbrain_requests.labels(**labels).inc()
        self.gbrain_duration.labels(**labels).observe(duration_seconds)

    def set_pending_index(self, *, jobs: int, oldest_age_seconds: float) -> None:
        self.pending_jobs.labels(**self.base).set(jobs)
        self.oldest_pending_age.labels(**self.base).set(oldest_age_seconds)

    def record_retry(self, *, outcome: str) -> None:
        self.retry_jobs.labels(**self._labels(outcome=outcome)).inc()

    def record_mcp(self, *, tool: str, outcome: str, duration_seconds: float) -> None:
        tool = self.normalizer.fixed(tool, MCP_TOOLS)
        labels = self._labels(tool=tool, outcome=outcome)
        self.mcp_requests.labels(**labels).inc()
        self.mcp_duration.labels(**labels).observe(duration_seconds)

    def record_mcp_auth_failure(self, *, reason: str) -> None:
        self.mcp_auth_failures.labels(**self._labels(reason=reason)).inc()

    def record_auth(self, *, surface: str, outcome: str, legacy: bool) -> None:
        self.auth_requests.labels(
            **self._labels(surface=surface, outcome=outcome, legacy=str(legacy).lower())
        ).inc()

    def record_auth_denial(self, *, operation: str, domain: str) -> None:
        self.auth_denials.labels(
            **self._labels(operation=operation, domain=domain)
        ).inc()

    def record_section_read(self, *, policy: str) -> None:
        self.section_reads.labels(**self._labels(policy=policy)).inc()

    def set_token_counts(self, *, active: int, revoked: int, expired: int) -> None:
        for status, value in {
            "active": active, "revoked": revoked, "expired": expired
        }.items():
            self.token_counts.labels(**self._labels(status=status)).set(value)

    def set_readiness(self, *, ready: bool) -> None:
        self.readiness.labels(**self.base).set(1 if ready else 0)

    def render(self) -> bytes:
        return generate_latest(self.registry)

    def shutdown(self) -> None:
        return None


class OpenTelemetryMetricsRecorder:
    def __init__(
        self,
        provider: MeterProvider,
        *,
        service: str,
        environment: str,
        allowed_projects: Iterable[str],
    ) -> None:
        self.provider = provider
        self.normalizer = LabelNormalizer(allowed_projects)
        self.base = {"service": service, "environment": environment}
        meter = provider.get_meter("research-library")
        self.search_requests = meter.create_counter("memento_context_search_requests")
        self.search_duration = meter.create_histogram(
            "memento_context_search_duration_seconds", unit="s"
        )
        self.search_hits = meter.create_histogram("memento_context_search_hits")
        self.search_blocks = meter.create_histogram("memento_context_search_blocks")
        self.publish_requests = meter.create_counter("memento_context_publish_requests")
        self.publish_duration = meter.create_histogram(
            "memento_context_publish_duration_seconds", unit="s"
        )
        self.supersedes = meter.create_counter("memento_context_supersedes")
        self.consulted_sources = meter.create_histogram("memento_context_consulted_sources")
        self.gbrain_requests = meter.create_counter("gbrain_operation_requests")
        self.gbrain_duration = meter.create_histogram("gbrain_operation_duration_seconds", unit="s")
        self.pending_jobs = meter.create_gauge("library_pending_index_jobs")
        self.oldest_pending_age = meter.create_gauge(
            "library_oldest_pending_index_age_seconds", unit="s"
        )
        self.retry_jobs = meter.create_counter("library_retry_jobs")
        self.mcp_requests = meter.create_counter("mcp_requests")
        self.mcp_duration = meter.create_histogram("mcp_request_duration_seconds", unit="s")
        self.mcp_auth_failures = meter.create_counter("mcp_auth_failures")
        self.auth_requests = meter.create_counter("library_auth_requests")
        self.auth_denials = meter.create_counter("library_auth_denials")
        self.section_reads = meter.create_counter("library_section_reads")
        self.token_counts = meter.create_gauge("library_access_tokens")
        self.readiness = meter.create_gauge("library_readiness")
        self.heartbeat = meter.create_gauge("library_observability_heartbeat")
        self.heartbeat.set(1, self.base)

    def _attributes(self, **values: str) -> dict[str, str]:
        return {**self.base, **values}

    def record_memento_search(
        self,
        *,
        outcome: str,
        project: str,
        duration_seconds: float,
        hit_count: int,
        block_counts: dict[str, int],
    ) -> None:
        project = self.normalizer.project(project)
        attributes = self._attributes(outcome=outcome, project=project)
        self.search_requests.add(1, attributes)
        self.search_duration.record(duration_seconds, attributes)
        self.search_hits.record(hit_count, self._attributes(project=project))
        for block, count in block_counts.items():
            self.search_blocks.record(
                count,
                self._attributes(
                    block=self.normalizer.fixed(block, MEMENTO_BLOCKS),
                    project=project,
                ),
            )

    def record_memento_publish(
        self,
        *,
        kind: str,
        outcome: str,
        project: str,
        duration_seconds: float,
        supersedes: bool,
        consulted_sources: int,
    ) -> None:
        kind = self.normalizer.fixed(kind, MEMENTO_KINDS)
        project = self.normalizer.project(project)
        attributes = self._attributes(kind=kind, outcome=outcome, project=project)
        self.publish_requests.add(1, attributes)
        self.publish_duration.record(duration_seconds, attributes)
        if supersedes:
            self.supersedes.add(1, self._attributes(kind=kind, project=project))
        self.consulted_sources.record(
            consulted_sources, self._attributes(kind=kind, project=project)
        )

    def record_gbrain(self, *, operation: str, outcome: str, duration_seconds: float) -> None:
        attributes = self._attributes(
            operation=self.normalizer.fixed(operation, GBRAIN_OPERATIONS),
            outcome=outcome,
        )
        self.gbrain_requests.add(1, attributes)
        self.gbrain_duration.record(duration_seconds, attributes)

    def set_pending_index(self, *, jobs: int, oldest_age_seconds: float) -> None:
        self.pending_jobs.set(jobs, self.base)
        self.oldest_pending_age.set(oldest_age_seconds, self.base)

    def record_retry(self, *, outcome: str) -> None:
        self.retry_jobs.add(1, self._attributes(outcome=outcome))

    def record_mcp(self, *, tool: str, outcome: str, duration_seconds: float) -> None:
        attributes = self._attributes(
            tool=self.normalizer.fixed(tool, MCP_TOOLS), outcome=outcome
        )
        self.mcp_requests.add(1, attributes)
        self.mcp_duration.record(duration_seconds, attributes)

    def record_mcp_auth_failure(self, *, reason: str) -> None:
        self.mcp_auth_failures.add(1, self._attributes(reason=reason))

    def record_auth(self, *, surface: str, outcome: str, legacy: bool) -> None:
        self.auth_requests.add(
            1,
            self._attributes(
                surface=surface, outcome=outcome, legacy=str(legacy).lower()
            ),
        )

    def record_auth_denial(self, *, operation: str, domain: str) -> None:
        self.auth_denials.add(1, self._attributes(operation=operation, domain=domain))

    def record_section_read(self, *, policy: str) -> None:
        self.section_reads.add(1, self._attributes(policy=policy))

    def set_token_counts(self, *, active: int, revoked: int, expired: int) -> None:
        self.token_counts.set(active, self._attributes(status="active"))
        self.token_counts.set(revoked, self._attributes(status="revoked"))
        self.token_counts.set(expired, self._attributes(status="expired"))

    def set_readiness(self, *, ready: bool) -> None:
        self.readiness.set(1 if ready else 0, self.base)

    def shutdown(self) -> None:
        self.provider.shutdown()


class CompositeMetricsRecorder:
    def __init__(self, recorders: Iterable[MetricsRecorder]) -> None:
        self.recorders = list(recorders)

    def _call(self, method: str, **values: object) -> None:
        for recorder in self.recorders:
            try:
                getattr(recorder, method)(**values)
            except Exception:
                # Telemetry must never break application work.
                continue

    def record_memento_search(self, **values: object) -> None:
        self._call("record_memento_search", **values)

    def record_memento_publish(self, **values: object) -> None:
        self._call("record_memento_publish", **values)

    def record_gbrain(self, **values: object) -> None:
        self._call("record_gbrain", **values)

    def set_pending_index(self, **values: object) -> None:
        self._call("set_pending_index", **values)

    def record_retry(self, **values: object) -> None:
        self._call("record_retry", **values)

    def record_mcp(self, **values: object) -> None:
        self._call("record_mcp", **values)

    def record_mcp_auth_failure(self, **values: object) -> None:
        self._call("record_mcp_auth_failure", **values)

    def record_auth(self, **values: object) -> None:
        self._call("record_auth", **values)

    def record_auth_denial(self, **values: object) -> None:
        self._call("record_auth_denial", **values)

    def record_section_read(self, **values: object) -> None:
        self._call("record_section_read", **values)

    def set_token_counts(self, **values: object) -> None:
        self._call("set_token_counts", **values)

    def set_readiness(self, **values: object) -> None:
        self._call("set_readiness", **values)

    def shutdown(self) -> None:
        for recorder in self.recorders:
            try:
                recorder.shutdown()
            except Exception:
                continue
