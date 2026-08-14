# Experiment report contract

Required fields: `experiment_external_id`, `iteration_external_id`, `report_version`, `title`,
`summary`. Include `code_revision`, configuration summary, metrics summary, conclusions,
limitations, and selected upload IDs when available.

Idempotency key format:

```text
autoresearch:<experiment_id>:<iteration_id>:<report_version>
```
