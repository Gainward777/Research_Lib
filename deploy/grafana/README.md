# Grafana Cloud assets

This directory contains versioned, content-free observability assets for Research
Library.

- `research-library.dashboard.json` is imported as a Grafana dashboard. Select
  the Grafana Cloud Prometheus data source when prompted.
- `alerts.yaml` is a Prometheus-compatible rules file for Grafana Cloud Metrics.
  Upload it with the Grafana Cloud rules API or `mimirtool rules load`.
- Configure contact points in Grafana Cloud for the target organization. Contact
  addresses and API credentials are intentionally not stored in Git.

Before importing rules, verify that the metric names exposed by the selected
Grafana Cloud data source match the OTLP translation used by the stack. The rules
exclude validation errors and idempotency conflicts from availability alerts.

The versioned rules include `library_readiness` and an OTLP heartbeat. Railway
must poll `/readyz` for the readiness gauge to stay current. An additional
Grafana Synthetic Monitoring probe is recommended because it also detects
network and routing failures before the application can emit a metric. The
exporter remains fail-safe and cannot make library requests fail.
