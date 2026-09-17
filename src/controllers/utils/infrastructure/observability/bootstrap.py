from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

from controllers.utils.bootstrap.settings import Settings
from controllers.utils.infrastructure.observability.metrics import (
    CompositeMetricsRecorder,
    MetricsRecorder,
    NoOpMetricsRecorder,
    OpenTelemetryMetricsRecorder,
    PrometheusMetricsRecorder,
)


@dataclass
class ObservabilityRuntime:
    recorder: MetricsRecorder
    prometheus: PrometheusMetricsRecorder | None = None

    def render_metrics(self) -> bytes:
        return self.prometheus.render() if self.prometheus is not None else b""

    @property
    def metrics_content_type(self) -> str:
        if self.prometheus is None:
            return PrometheusMetricsRecorder.content_type
        return self.prometheus.content_type

    def shutdown(self) -> None:
        self.recorder.shutdown()


_runtime: ObservabilityRuntime | None = None
_fingerprint: tuple[object, ...] | None = None
_lock = RLock()


def _settings_fingerprint(settings: Settings) -> tuple[object, ...]:
    return (
        settings.metrics_enabled,
        settings.metrics_endpoint_enabled,
        settings.otel_service_name,
        settings.otel_service_version,
        settings.otel_deployment_environment,
        settings.otel_metrics_exporter,
        settings.otel_exporter_otlp_endpoint,
        settings.otel_exporter_otlp_headers.get_secret_value(),
        settings.otel_export_timeout_seconds,
        settings.otel_max_export_batch_size,
        settings.otel_export_interval_milliseconds,
        tuple(settings.metrics_allowed_projects),
    )


def get_observability(settings: Settings) -> ObservabilityRuntime:
    global _fingerprint, _runtime
    fingerprint = _settings_fingerprint(settings)
    with _lock:
        if _runtime is not None and _fingerprint == fingerprint:
            return _runtime
        if _runtime is not None:
            _runtime.shutdown()

        recorders: list[MetricsRecorder] = []
        prometheus = None
        if settings.metrics_endpoint_enabled:
            prometheus = PrometheusMetricsRecorder(
                service=settings.otel_service_name,
                environment=settings.otel_deployment_environment,
                allowed_projects=settings.metrics_allowed_projects,
            )
            recorders.append(prometheus)

        if settings.metrics_enabled and settings.otel_metrics_exporter == "otlp":
            exporter = OTLPMetricExporter(
                endpoint=settings.otel_exporter_otlp_endpoint,
                headers=_parse_headers(settings.otel_exporter_otlp_headers.get_secret_value()),
                timeout=settings.otel_export_timeout_seconds,
                max_export_batch_size=settings.otel_max_export_batch_size,
            )
            reader = PeriodicExportingMetricReader(
                exporter,
                export_interval_millis=settings.otel_export_interval_milliseconds,
            )
            provider = MeterProvider(
                metric_readers=[reader],
                resource=Resource.create(
                    {
                        "service.name": settings.otel_service_name,
                        "service.version": settings.otel_service_version,
                        "deployment.environment.name": (settings.otel_deployment_environment),
                    }
                ),
            )
            recorders.append(
                OpenTelemetryMetricsRecorder(
                    provider,
                    allowed_projects=settings.metrics_allowed_projects,
                )
            )

        if not recorders:
            recorder: MetricsRecorder = NoOpMetricsRecorder()
        else:
            recorder = CompositeMetricsRecorder(recorders)

        _runtime = ObservabilityRuntime(recorder=recorder, prometheus=prometheus)
        _fingerprint = fingerprint
        return _runtime


def shutdown_observability() -> None:
    global _fingerprint, _runtime
    with _lock:
        if _runtime is not None:
            _runtime.shutdown()
        _runtime = None
        _fingerprint = None


def _parse_headers(raw: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for part in raw.split(","):
        name, separator, value = part.partition("=")
        if separator and name.strip() and value.strip():
            headers[name.strip()] = value.strip()
    return headers
