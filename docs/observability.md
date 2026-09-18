# Observability Research Library

## Что реализовано

Приложение публикует агрегированные метрики Memento, GBrain, MCP и очереди
индексации. В stdout пишутся JSON-события с `request_id`. Тексты запросов,
материалов, MCP payload и токены в телеметрию не передаются.

Durable provenance хранится отдельно от метрик: поле
`consulted_context_item_ids` сохраняется в Memento frontmatter и создаёт
отношения `has-source`.

## Режимы

По умолчанию observability выключена и используется no-op recorder.

Для Grafana Cloud включите OTLP export:

```text
METRICS_ENABLED=true
OTEL_SERVICE_NAME=research-library
OTEL_SERVICE_VERSION=0.1.0
OTEL_DEPLOYMENT_ENVIRONMENT=production
OTEL_METRICS_EXPORTER=otlp
OTEL_EXPORTER_OTLP_ENDPOINT=https://<grafana-cloud-otlp-endpoint>
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic <secret>
OTEL_EXPORT_INTERVAL_MILLISECONDS=15000
OTEL_EXPORT_TIMEOUT_SECONDS=10
OTEL_MAX_EXPORT_BATCH_SIZE=512
METRICS_ALLOWED_PROJECTS=platform,research
```

`METRICS_ALLOWED_PROJECTS` — закрытый список project labels. Любое неизвестное
значение превращается в `_unknown`, чтобы пользовательский текст не создавал
неограниченную cardinality.

Для локального Prometheus-compatible endpoint дополнительно задайте:

```text
METRICS_ENDPOINT_ENABLED=true
METRICS_AUTH_TOKEN=<отдельный случайный секрет>
```

Без `METRICS_AUTH_TOKEN` приложение не запускается при включённом endpoint.
Токен не должен совпадать с `LIBRARY_API_TOKEN` или `MCP_AUTH_TOKEN`.

Проверка:

```bash
curl -H "Authorization: Bearer $METRICS_AUTH_TOKEN" \
  https://<railway-domain>/metrics
```

Маршрут `/metrics` исключён из OpenAPI. Если endpoint выключен, он возвращает
404; при неверном токене — 401.

## Корреляция с Railway logs

Каждый HTTP-запрос получает `X-Request-ID`. Корректный входящий идентификатор
сохраняется, иначе приложение генерирует новый. Тот же идентификатор возвращается
в response header и попадает в JSON-логи операций Memento, GBrain и MCP.

Bearer-токен в лог не записывается. Для диагностики используется только
`principal_id` — укороченный SHA-256 hash токена.

Поиск причины сбоя:

1. В Grafana выберите временной интервал, service, environment и project.
2. В Railway logs найдите событие этого типа и времени.
3. Скопируйте `request_id` и отфильтруйте по нему остальные события.
4. Для истории решения откройте Memento item и его `has-source` relations.

## Grafana assets

Versioned assets находятся в `deploy/grafana/`:

- `research-library.dashboard.json` — Memento, GBrain, MCP, retry и retrieval;
- `alerts.yaml` — error ratio, latency, GBrain timeout, pending-index age,
  readiness, retrieval baseline и отсутствие OTLP heartbeat;
- `README.md` — порядок импорта и внешние ограничения.

Contact points и credentials создаются в Grafana Cloud и Railway, но не
коммитятся. Railway должен регулярно опрашивать `/readyz`; внешний HTTP probe
через Grafana Synthetic Monitoring остаётся рекомендуемой независимой проверкой.

## Отказоустойчивость

Запись метрик обёрнута fail-safe recorder: исключение observability backend не
прерывает REST, MCP, Telegram или retry worker. SDK хранит агрегаты, а не очередь
отдельных событий; cardinality ограничена фиксированными labels. OTLP export
выполняется отдельным periodic reader с ограниченным batch size и timeout. При
недоступности Grafana основные операции продолжают работать; отсутствие
heartbeat видно в Grafana, а подробности exporter — в Railway logs.

## Проверка перед production

1. Создайте Grafana Cloud stack и отдельные OTLP credentials.
2. Добавьте переменные только в Railway Variables.
3. Выполните публикацию и поиск Memento через MCP.
4. Убедитесь, что dashboard получает found/empty/outcome и latency.
5. Проверьте JSON-события в Railway logs и корреляцию по `request_id`.
6. Искусственно вызовите GBrain timeout и pending-index retry.
7. Убедитесь, что query, content, item IDs и токены отсутствуют в metrics.
8. Отключите OTLP endpoint и повторите поиск/публикацию: запросы должны работать.
