# План добавления observability для Memento

## 1. Цель

Добавить production-наблюдаемость для одновременной работы нескольких
разработчиков и внешних агентов с Research Library.

Система должна позволять:

- обнаруживать деградацию поиска и публикации контекста;
- отличать пустой результат поиска от ошибки GBrain;
- находить причину конкретного сбоя по `request_id` в Railway logs;
- контролировать индексацию durable Markdown;
- оценивать качество retrieval на основе реально использованных материалов;
- строить dashboards и alerts без чтения пользовательского содержимого;
- не блокировать работу Библиотеки при недоступности observability backend.

## 2. Целевая архитектура

Основной вариант — managed Grafana Cloud как единый внешний сервис для
Prometheus-совместимых метрик, dashboards и alerts. Research Library отправляет
метрики по OTLP/HTTPS. Структурированные JSON-логи пишутся только в
`stdout/stderr` и собираются Railway.

```text
Codex / Cursor / Claude Code
             |
             | MCP
             v
Research Library on Railway
  ├── metrics ──OTLP/HTTPS──> Grafana Cloud
  │                            ├── dashboards
  │                            └── alerts
  ├── JSON stdout ───────────> Railway logs
  └── has-source ────────────> Markdown / GBrain
```

Grafana не запускается в контейнере Research Library. Loki, Tempo и
распределённая трассировка не входят в текущий релиз. Их добавление допускается
позже, если Railway logs перестанут обеспечивать необходимый поиск или сервис
будет разделён на несколько процессов.

## 3. Разделение данных

### 3.1. Метрики

Агрегированные числовые временные ряды. Они отвечают на вопросы «когда»,
«насколько часто» и «насколько медленно», но не содержат детали конкретного
материала.

### 3.2. Логи

Отдельные диагностические события. Они содержат `request_id`, этап,
outcome и безопасные идентификаторы, но не содержат текст запроса или материала.

### 3.3. Durable provenance

`consulted_context_item_ids` не является телеметрией. Это постоянная связь между
знаниями. Она сохраняется в frontmatter Memento-страницы и отношениями
`has-source` в графе GBrain.

Метрики хранятся в Grafana Cloud, логи — в Railway с retention выбранного плана.
Durable provenance хранится в Research Library и попадает в резервные копии.

## 4. Корреляция

Каждый входящий REST или MCP-запрос получает:

- `request_id` — прикладной идентификатор запроса;
- `principal_id` — безопасный идентификатор токена или клиента только для логов;
- `project` и `repository` — нормализованные scope-значения.

Диагностика выполняется по временному интервалу, service/project/outcome метрики и
`request_id` конкретного события:

```text
metric time window
    |
    v
Railway log -> request_id -> operation / item_id / error code
    |
    v
Memento item -> has-source relations
```

`request_id`, `item_id`, Linear ID и commit не используются как metric labels.
Они остаются в Railway logs и durable metadata.

## 5. Метрики

### 5.1. Поиск контекста

```text
memento_context_search_requests_total{outcome,project}
memento_context_search_duration_seconds{outcome,project}
memento_context_search_hits{project}
memento_context_search_blocks{block,project}
```

`outcome`:

- `found`;
- `empty`;
- `validation_error`;
- `gbrain_error`;
- `internal_error`.

`block`:

- `related_implementations`;
- `decisions`;
- `known_problems`;
- `tests_and_evidence`;
- `checkpoints`.

### 5.2. Публикация контекста

```text
memento_context_publish_requests_total{kind,outcome,project}
memento_context_publish_duration_seconds{kind,outcome,project}
memento_context_supersedes_total{kind,project}
memento_context_consulted_sources{kind,project}
```

`outcome`:

- `created`;
- `deduplicated`;
- `pending_index`;
- `validation_error`;
- `idempotency_conflict`;
- `gbrain_error`;
- `internal_error`.

### 5.3. GBrain и индексация

```text
gbrain_operation_requests_total{operation,outcome}
gbrain_operation_duration_seconds{operation,outcome}
library_pending_index_jobs
library_oldest_pending_index_age_seconds
library_retry_jobs_total{outcome}
```

`operation` ограничивается фиксированным набором: `search`, `get`, `put`,
`think`, `health`, `reindex`.

### 5.4. MCP

```text
mcp_requests_total{tool,outcome}
mcp_request_duration_seconds{tool,outcome}
mcp_auth_failures_total{reason}
```

Названия tools имеют фиксированный каталог и допустимы как label.

## 6. Ограничение cardinality и конфиденциальность

Разрешённые labels:

- `service`;
- `environment`;
- `operation`;
- `tool`;
- `outcome`;
- `context_kind`;
- `block`;
- `verification`;
- `project` из контролируемого project registry.

Запрещённые labels:

- текст поискового запроса;
- `request_id`;
- Linear ID и `work_context_id`;
- `item_id`;
- commit, branch и path;
- пользователь или Telegram ID;
- repository, пока его список не ограничен конфигурацией;
- токены, секреты и содержимое материалов.

Неизвестный или незарегистрированный project нормализуется в `_unknown`.
Значения labels не принимаются напрямую из произвольного пользовательского текста.

## 7. Схема структурированного лога

Пример события:

```json
{
  "timestamp": "2026-09-17T12:00:00Z",
  "level": "INFO",
  "event": "memento.context.search.completed",
  "service": "research-library",
  "environment": "production",
  "request_id": "req_...",
  "principal_id": "principal_...",
  "project": "platform",
  "repository": "backend-api",
  "work_item": "BUG-731",
  "outcome": "found",
  "duration_ms": 418,
  "hit_count": 6,
  "error_code": null
}
```

Допустимо логировать идентификаторы и error codes. Запрещено логировать:

- `query` и `content`;
- полный MCP payload;
- HTTP Authorization header;
- OpenAI key, MCP token или Telegram token;
- содержимое найденных документов;
- stack trace на INFO level.

Railway получает JSON-строки непосредственно через `stdout`. Приложение не
отправляет логи в Grafana Cloud и не зависит от внешнего log backend.

## 8. Использованные источники контекста

В `PublishDevelopmentContext` добавляется:

```yaml
consulted_context_item_ids:
  - lib_123
  - lib_456
```

При публикации сервис:

1. проверяет существование каждого item;
2. сохраняет ID в frontmatter;
3. создаёт отношение `has-source` от новой записи к каждому источнику;
4. увеличивает histogram `memento_context_consulted_sources` на количество связей;
5. не отправляет сами item IDs в metrics.

Это позволяет измерять практическое использование retrieval и сохраняет
проверяемую историю происхождения решений.

## 9. Размещение кода

Соблюдается существующая MVC-архитектура:

```text
src/
├── controllers/
│   ├── api/
│   │   └── metrics_controller.py
│   ├── mcp/
│   │   └── observability_middleware.py
│   └── utils/
│       └── infrastructure/
│           └── observability/
│               ├── __init__.py
│               ├── bootstrap.py
│               ├── metrics.py
│               ├── logging.py
│               └── context.py
└── views/
    └── api/
        └── metrics_view.py
```

MementoService получает абстракцию recorder через dependency container. Бизнес-
логика не импортирует Grafana SDK и не знает адрес observability backend.

## 10. Зависимости

Планируемые библиотеки:

```text
opentelemetry-api
opentelemetry-sdk
opentelemetry-exporter-otlp-proto-http
prometheus-client
```

`prometheus-client` используется для локального `/metrics` и self-hosted режима.
В production основным транспортом является OTLP/HTTPS.

## 11. Конфигурация Railway

```text
METRICS_ENABLED=true
OTEL_SERVICE_NAME=research-library
OTEL_SERVICE_VERSION=0.1.0
OTEL_DEPLOYMENT_ENVIRONMENT=production
OTEL_METRICS_EXPORTER=otlp
OTEL_EXPORTER_OTLP_ENDPOINT=https://<grafana-cloud-otlp-endpoint>
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic <secret>
OTEL_EXPORT_INTERVAL_MILLISECONDS=15000
METRICS_ENDPOINT_ENABLED=true
METRICS_AUTH_TOKEN=<separate-secret>
```

Секреты создаются только в Railway Variables. Они не записываются в `.env.example`
с реальными значениями, логи или Memento.

Недоступность OTLP endpoint не влияет на `/healthz` и `/readyz`. Exporter имеет
bounded queue, batch export, timeout и сбрасывает телеметрию при переполнении,
не блокируя MCP/REST/Telegram.

## 12. Grafana dashboards

### 12.1. Memento Overview

- search и publish requests per minute;
- found/empty/error ratio;
- p50/p95/p99 latency;
- hits per search;
- публикации по context kind;
- количество consulted sources;
- pending index jobs и возраст старейшего задания.

### 12.2. GBrain

- latency и errors по операциям;
- search/put/think throughput;
- timeouts;
- pending/retry indexing;
- readiness failures.

### 12.3. MCP

- requests по tools;
- auth failures;
- latency и errors;
- активность проектов без идентификации отдельных разработчиков.

### 12.4. Retrieval Quality

- empty search ratio по проектам;
- распределение количества hits;
- заполненность фиксированных blocks;
- доля публикаций с `consulted_context_item_ids`;
- среднее количество использованных источников;
- доля superseded записей.

Dashboards хранятся как versioned provisioning JSON или Terraform в репозитории,
а не настраиваются только вручную через UI.

## 13. Alerts и начальные SLO

Начальные значения пересматриваются после двух недель эксплуатации.

```text
Search availability:        >= 99.5%
Publish availability:       >= 99.5%
Search p95:                 <= 10 s
Publish p95:                <= 10 s
Pending index age:          < 10 min
```

Alerts:

- error ratio > 5% за 10 минут;
- GBrain timeout появился 3 раза за 10 минут;
- p95 search или publish > 10 секунд за 15 минут;
- oldest pending index > 10 минут;
- `/readyz` не готов 3 минуты;
- empty search ratio вырос в 2 раза относительно семидневного baseline;
- OTLP exporter теряет batches более 5 минут.

Validation errors и idempotency conflicts не входят в availability SLO, но имеют
отдельные панели и alerts при резком росте.

## 14. Retention

Начальные значения:

- metrics в Grafana Cloud — 90 дней;
- JSON-логи — согласно retention выбранного тарифа Railway;
- durable Memento provenance — без автоматического удаления.

Retention метрик настраивается в Grafana Cloud. Retention логов задаётся средствами
Railway; Loki в этой версии не используется. Политики пересматриваются по стоимости
и реальному объёму.

## 15. Этапы реализации

### Этап 1. Provisioning

- [ ] Создать Grafana Cloud stack.
- [ ] Создать отдельные credentials для OTLP ingestion.
- [ ] Добавить Railway Variables.
- [ ] Проверить отправку тестовой метрики и появление JSON-лога в Railway.

### Этап 2. Observability core

- [x] Добавить OpenTelemetry dependencies.
- [x] Реализовать bootstrap, graceful shutdown и no-op режим.
- [x] Добавить `request_id` и JSON logging.
- [x] Добавить безопасную нормализацию labels.
- [x] Обеспечить неблокирующий periodic export с bounded batch и timeout.

### Этап 3. Инструментирование Memento и GBrain

- [x] Инструментировать `library_get_context`.
- [x] Инструментировать `library_publish_context`.
- [x] Инструментировать GBrain search/index/think/health.
- [x] Добавить pending-index gauges.
- [x] Покрыть outcomes и latency тестами.

### Этап 4. Durable provenance

- [x] Добавить `consulted_context_item_ids` в модель.
- [x] Валидировать источники.
- [x] Создавать `has-source` relations.
- [x] Покрыть идемпотентность и supersedes тестами.

### Этап 5. Metrics endpoint и безопасность

- [x] Добавить `/metrics` для локального/self-hosted режима.
- [x] Защитить endpoint отдельным `METRICS_AUTH_TOKEN`.
- [x] Исключить `/metrics` из OpenAPI и документировать только с авторизацией.
- [x] Добавить тесты отсутствия чувствительных labels и payload.

### Этап 6. Grafana assets

- [x] Создать versioned dashboard.
- [x] Создать versioned alert rules.
- [ ] Импортировать dashboard/rules в Grafana Cloud и настроить contact points.
- [x] Добавить в alert временной интервал, service и project для поиска в Railway logs.
- [ ] Проверить dashboards под параллельной нагрузкой нескольких агентов.

### Этап 7. Проверка отказов

- [x] Unit-проверить, что исключение metrics backend не ломает приложение.
- [ ] Проверить реальный outage Grafana Cloud на Railway.
- [ ] Проверить переполнение exporter queue.
- [x] Проверить GBrain timeout и pending index.
- [x] Проверить отсутствие содержимого запросов в telemetry.
- [ ] Провести нагрузочный тест одновременных MCP-клиентов.

## 16. Критерии готовности

1. Один MCP-запрос создаёт метрику и структурированный Railway log с `request_id`.
2. По `request_id` в Railway logs видны outcome, длительность и безопасный код ошибки или ID материала.
3. Grafana dashboard показывает found/empty/error, latency и pending index.
4. Alert срабатывает на искусственный GBrain timeout.
5. Недоступность Grafana Cloud не ломает поиск или публикацию.
6. Query, content и токены отсутствуют в metric labels и логах; document IDs отсутствуют в metric labels.
7. `consulted_context_item_ids` создаёт durable `has-source` relations.
8. Повторная публикация не удваивает relation и учитывается отдельным outcome.
9. Несколько разработчиков могут работать параллельно без смешивания `request_id`.
10. Все существующие тесты Research Library продолжают проходить.

## 17. Порядок внедрения

Реализацию начинать с observability core и инструментирования Memento. Grafana
Cloud stack создаётся в начале, чтобы каждый следующий этап проверялся на реальном
backend, а не только локальными mocks. Dashboards и alerts добавляются после
появления первых реальных временных рядов, но входят в тот же релиз.
