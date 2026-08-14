# Research Library

Рабочая реализация архитектурного плана находится в `src/`. Актуальная структура и
архитектурные решения описаны в [`arch.md`](arch.md), команды установки, запуска,
проверки REST, Telegram, MCP и GBrain — в [`DEVELOPMENT.md`](DEVELOPMENT.md).

Ниже сохранён исходный подробный план продукта.

---
# План нового репозитория `research-library`

## 1. Назначение

`research-library` — самостоятельный сервис исследовательской библиотеки,
работающий независимо от внешних исследовательских сервисов и RunPod.

Сервис должен:

- принимать пересланные Telegram-сообщения с изображениями;
- принимать обычные заметки, идеи, ссылки и публикации через Telegram;
- принимать итоговые отчёты внешних сервисов напрямую через API/MCP, без
  Telegram;
- хранить знания как Markdown-страницы и изображения на persistent volume;
- использовать GBrain с PGLite для полнотекстового, векторного и графового
  поиска;
- отвечать на вопросы к библиотеке естественным языком через Telegram;
- разделять отчёты, идеи, публикации, методы и другие типы с помощью
  исследовательского GBrain schema pack;
- переживать restart/redeploy без потери принятых материалов;
- позволять позже перейти с PGLite на PostgreSQL без изменения внешних
  контрактов.

Сервис **не** управляет выполнением экспериментов. Runs, iterations, PID,
checkpoints, quota pause и resume state принадлежат AutoResearch Control Plane.
В библиотеку поступают только устойчивые результаты и знания.

## 2. Принятые архитектурные решения

### 2.1. Источники истины

```text
Markdown brain repo + attachments
    источник библиотечных знаний

GBrain PGLite
    производный индекс, embeddings и knowledge graph

SQLite
    служебное состояние Telegram ingestion, uploads и retry queue

AutoResearch PostgreSQL
    состояние выполнения экспериментов; находится вне этого сервиса
```

Всё ценное, созданное библиотекарем, должно попадать в Markdown/frontmatter.
PGLite должен быть перестраиваемым индексом. На первом этапе не использовать
DB-only enrichment, Minions и автономный dream cycle GBrain.

### 2.2. Obsidian

Obsidian не является зависимостью проекта. Markdown brain сохраняет
совместимость с Obsidian, но сервис не устанавливает и не запускает Obsidian,
Obsidian Sync или Obsidian Headless.

### 2.3. GBrain

- закрепить точную версию или commit GBrain; не устанавливать `master/latest`
  при каждом deploy;
- использовать PGLite на persistent volume;
- включить один writer и одну Railway replica;
- выполнять mutating-операции через одну очередь;
- использовать `search` для дешёвого retrieval без синтеза;
- использовать `think/query` для ответа с LLM-синтезом и источниками;
- использовать собственный `research-v1` schema pack;
- оставить возможность миграции на отдельный PostgreSQL при росте нагрузки.

### 2.4. LLM

GBrain `think/query` является основным синтезатором ответов на вопросы.
Отдельный вызов модели допускается для:

- определения типа нового неструктурированного материала;
- выделения краткого заголовка, резюме, выводов и ключевых сущностей;
- предложения связей и изменений research schema;
- разрешения неоднозначного намерения пользователя.

Используется тот же провайдер/модель, что и для GBrain, если это технически
возможно. OCR не выполнять. Анализ изображений по умолчанию отключён.

## 3. Архитектура

```text
Telegram
    |
    v
Library Telegram Bot
    |
    +--> deterministic intent router
    |       |
    |       +--> ingestion pipeline
    |       +--> GBrain search
    |       +--> GBrain think/query
    |
    v
Library Service API / MCP facade
    |
    +--> Markdown writer
    +--> attachment store
    +--> SQLite operational store
    +--> serialized GBrain adapter
              |
              +--> PGLite
              +--> embeddings
              +--> graph

External research service
    |
    +--> HTTPS API or MCP facade
            |
            +--> library_save_experiment_report
            +--> library_save_idea
            +--> library_search
            +--> library_get
```

## 4. Как внешние сервисы подключаются к библиотеке

MCP-сервер принадлежит репозиторию `Research_Lib` и публикуется тем же
FastAPI-процессом по endpoint `/mcp`. Он имеет доступ к той же SQLite базе,
Markdown-файлам и persistent volume, что Telegram и REST API.

Внешний сервис находится в другом репозитории и содержит только MCP-клиент:

```text
External service repository
└── MCP client ──HTTPS──> Research_Lib /mcp
```

Внутренний GBrain adapter наружу не публикуется. Основной контракт для записи
экспериментального отчёта:

```text
library_save_experiment_report
```

REST endpoint остаётся дополнительным интерфейсом:

```http
POST /v1/experiment-reports
Idempotency-Key: autoresearch:<experiment_id>:<iteration_id>:<report_version>
Authorization: Bearer <service-token>
```

Сервис:

1. валидирует типизированный payload;
2. принимает файлы отдельными multipart uploads;
3. сжимает изображения;
4. атомарно сохраняет attachments;
5. формирует Markdown/frontmatter;
6. записывает страницу через GBrain adapter;
7. возвращает стабильные `library_item_id`, `slug` и ссылку на источник;
8. при повторе того же idempotency key возвращает прежний результат.

Telegram в этом потоке не участвует. Отправляющий сервис отвечает за durable
outbox и повтор доставки с тем же idempotency key. Library Service не получает
и не изменяет внутреннее состояние эксперимента.
## 5. Структура brain repo

```text
brain/
├── experiments/
├── reports/
├── ideas/
├── publications/
├── methods/
├── concepts/
├── models/
├── datasets/
├── sources/
│   ├── telegram/
│   └── autoresearch/
├── inbox/
├── attachments/
└── _system/
    ├── schemas/
    ├── templates/
    └── migrations/
```

Правила:

- один материал имеет один основной page type;
- дополнительные измерения задаются frontmatter, tags и relations;
- исходный Telegram-текст сохраняется без перезаписи;
- сомнительный материал попадает в `inbox`, а не в случайный тип;
- бинарные файлы не встраиваются в Markdown как base64;
- slug не является пользовательским идентификатором;
- стабильный `library_item_id` хранится во frontmatter;
- перемещение/переименование страницы не меняет `library_item_id`.

## 6. Research schema pack `research-v1`

### 6.1. Типы

```text
experiment
experiment-report
idea
publication
method
concept
model
dataset
source
note
```

Не создавать отдельный тип для каждой предметной области. LoRA, diffusion,
biology, benchmark и другие домены являются tags/properties/concepts.

### 6.2. Связи

```text
tests
supports
contradicts
motivated-by
derived-from
uses-method
uses-model
uses-dataset
described-by
produced
continues
related-to
has-source
```

### 6.3. Базовые поля

Все страницы:

```yaml
id: lib_...
type: experiment-report
title: ...
created_at: 2026-07-30T12:00:00Z
updated_at: 2026-07-30T12:00:00Z
source_kind: telegram
source_external_id: telegram:<chat_id>:<message_id>
authors: []
tags: []
related: []
schema_version: research-v1
```

Отчёт эксперимента дополнительно:

```yaml
experiment_external_id: ...
iteration_external_id: ...
code_revision: ...
status: completed
models: []
datasets: []
methods: []
metrics_summary: {}
artifact_ids: []
```

Не помещать длинные массивы метрик во frontmatter. В библиотеку передаётся
summary и ссылка на AutoResearch experiment record.

### 6.4. Эволюция схемы

Настройка:

```text
LIBRARY_SCHEMA_MUTATION_MODE=propose  # disabled | propose | auto
```

Первый production-режим — `propose`:

- библиотекарь автоматически создаёт tags, relations и aliases;
- новый page type или link type оформляется как schema proposal;
- proposal виден через Telegram и audit;
- применение выполняется scoped-кнопкой или административной командой;
- каждая mutation обратима и версионирована.

После накопления eval-набора отдельные безопасные mutation можно перевести в
`auto`.

## 7. Telegram UX

### 7.1. Приём материалов

Поддержать:

- пересланное сообщение с caption и фотографиями;
- Telegram media group по `media_group_id`;
- несколько сообщений в явной сессии `/collect` → `/save`;
- `/idea <text>`;
- `/paper <url-or-text>`;
- `/save <text>`;
- обычное сообщение с прикреплёнными изображениями;
- повтор Telegram update без дубликата.

Для одиночного forwarded message команда не нужна: forwarding трактуется как
добавление.

### 7.2. Запросы

```text
/search <query>     быстрый retrieval без LLM-синтеза
/ask <question>     GBrain think/query
/recent [type]
/item <id-or-slug>
/related <id-or-slug>
/collect
/save
/cancel
/schema
/health
```

Обычный текст:

1. deterministic router проверяет forward/media/active collection session;
2. явные команды обрабатываются без LLM;
3. вопросительный запрос идёт в `think`;
4. неоднозначный текст классифицируется одним bounded LLM-вызовом;
5. при низкой уверенности бот задаёт scoped-вопрос, а не сохраняет наугад.

### 7.3. Ответ после сохранения

Бот сообщает:

- что сохранено;
- выбранный тип;
- заголовок;
- количество изображений;
- выделенные ключевые сведения;
- созданные связи;
- `library_item_id` только как техническую ссылку, не как основной способ
  поиска.

## 8. Изображения

OCR не реализовывать.

Pipeline:

1. получить Telegram `file_id`;
2. скачать максимальный вариант, доступный Bot API;
3. проверить фактический MIME и лимит размера;
4. применить ориентацию;
5. не увеличивать изображение;
6. уменьшить по длинной стороне;
7. сохранить во временный файл;
8. вычислить SHA-256;
9. выполнить atomic rename;
10. связать attachment с library item.

Переменные:

```text
LIBRARY_IMAGE_MAX_LONG_SIDE_PX=2048
LIBRARY_IMAGE_FORMAT=webp
LIBRARY_IMAGE_QUALITY=85
LIBRARY_KEEP_ORIGINALS=false
LIBRARY_IMAGE_VISION_ANALYSIS=false
```

Если файл отправлен как Telegram Photo, сохраняется доступная Telegram-версия.
Если как Document, можно сохранить исходный файл.

Путь:

```text
attachments/<library_item_id>/<sha256-prefix>-<safe-name>.<ext>
```

## 9. REST API

Версия API начинается с `/v1`.

### 9.1. Endpoints

```text
GET  /healthz
GET  /readyz

POST /v1/uploads
POST /v1/items
GET  /v1/items/{item_id}
POST /v1/items/{item_id}/relations

POST /v1/experiment-reports
POST /v1/ideas
POST /v1/publications

POST /v1/search
POST /v1/ask

GET  /v1/jobs/{job_id}
POST /v1/schema/proposals
GET  /v1/schema/proposals
POST /v1/schema/proposals/{proposal_id}/apply
```

### 9.2. Experiment report request

```json
{
  "source": "autoresearch",
  "experiment_external_id": "exp-123",
  "iteration_external_id": "iter-5",
  "report_version": 1,
  "title": "LoRA rank comparison",
  "summary": "Compared rank 8, 16 and 32...",
  "hypothesis": "Rank 16 should preserve identity better than rank 32.",
  "configuration": {
    "base_model": "SDXL",
    "steps": 500
  },
  "metrics_summary": {
    "best_loss": 0.091
  },
  "conclusions": [
    "Rank 32 overfits earlier."
  ],
  "limitations": [],
  "artifact_upload_ids": [
    "upload-..."
  ],
  "source_library_item_ids": [
    "lib_..."
  ],
  "autoresearch_url": null,
  "code_revision": "git-sha"
}
```

Response:

```json
{
  "item_id": "lib_...",
  "slug": "reports/2026/lo-ra-rank-comparison",
  "created": true,
  "indexed": true,
  "warnings": []
}
```

### 9.3. Search request

```json
{
  "query": "LoRA SDXL overfitting around 500 steps",
  "types": ["experiment-report", "idea", "publication"],
  "tags": [],
  "limit": 10,
  "synthesize": false
}
```

`synthesize=false` использует GBrain search. `synthesize=true` использует
GBrain think/query.

### 9.4. Идемпотентность

- все mutating service-to-service запросы требуют `Idempotency-Key`;
- Telegram использует `telegram:<chat_id>:<message_id>`;
- media group использует `telegram-group:<chat_id>:<media_group_id>`;
- AutoResearch использует
  `autoresearch:<experiment_id>:<iteration_id>:<report_version>`;
- повтор возвращает прежний status/body;
- несовпадающий payload с тем же ключом возвращает conflict.

## 10. MCP facade

MCP endpoint: `POST /mcp` по протоколу Streamable HTTP. При заданном
`MCP_AUTH_TOKEN` клиент передаёт `Authorization: Bearer <token>`.

Минимальный внешний набор:

```text
library_search                  read-only
library_get                     read-only
library_get_related             read-only
library_save_experiment_report  write
library_save_idea               write
library_save_publication        write
```

Административные schema mutations, удаление страниц и внутренний GBrain наружу
не раскрываются. Клиентские skills, prompts и fallback-скрипты не входят в
репозиторий библиотеки: если они нужны, ими владеет репозиторий внешнего сервиса.
## 11. SQLite operational schema

```text
telegram_updates
telegram_messages
telegram_media_groups
collection_sessions
ingest_requests
uploads
ingest_jobs
delivery_attempts
schema_proposals
```

Обязательные свойства:

- WAL mode;
- одна async write queue;
- уникальные external/idempotency keys;
- payload hash;
- retry counter и `next_attempt_at`;
- terminal statuses;
- отсутствие LLM secrets и Telegram token в БД.

SQLite не дублирует содержимое Markdown-страницы. Она хранит только receipt,
processing state и пути/идентификаторы.

## 12. Транзакционный ingestion pipeline

Состояния:

```text
received
  -> downloading
  -> stored_raw
  -> classifying
  -> writing_page
  -> indexing
  -> completed

Любой этап
  -> retryable_failed | permanently_failed
```

Гарантии:

- raw text receipt сохраняется до LLM-вызова;
- attachments пишутся атомарно;
- Markdown пишется через temporary file + atomic rename;
- GBrain index обновляется только после durable Markdown;
- ошибка GBrain не удаляет страницу: job становится `pending_index`;
- reindex job восстанавливает индекс после restart;
- один library item не создаётся повторно после retry;
- пользователь получает terminal result или понятное сообщение об ошибке.

## 13. Структура нового репозитория

```text
research-library/
├── src/research_library/
│   ├── main.py
│   ├── config.py
│   ├── domain.py
│   ├── errors.py
│   ├── api/
│   │   ├── app.py
│   │   ├── auth.py
│   │   ├── models.py
│   │   └── routes/
│   ├── telegram/
│   │   ├── bot.py
│   │   ├── router.py
│   │   ├── collection.py
│   │   └── rendering.py
│   ├── ingestion/
│   │   ├── service.py
│   │   ├── classifier.py
│   │   ├── idempotency.py
│   │   └── jobs.py
│   ├── storage/
│   │   ├── markdown.py
│   │   ├── attachments.py
│   │   └── sqlite.py
│   ├── gbrain/
│   │   ├── adapter.py
│   │   ├── process.py
│   │   ├── schemas.py
│   │   └── queue.py
│   ├── librarian/
│   │   ├── intent.py
│   │   ├── enrichment.py
│   │   └── answers.py
│   └── mcp/
│       ├── server.py
│       └── tools.py
├── schema-packs/research-v1/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/
├── scripts/
│   ├── bootstrap_gbrain.py
│   ├── rebuild_index.py
│   └── backup.py
├── migrations/
├── Dockerfile
├── pyproject.toml
├── uv.lock
├── .env.example
├── README.md
└── AGENTS.md
```

Предпочтительный Python stack:

- Python 3.11–3.13;
- `aiogram` 3.x;
- FastAPI + Uvicorn;
- `httpx`;
- `aiosqlite`;
- Pillow;
- Pydantic 2;
- pytest + pytest-asyncio.

GBrain устанавливается как отдельный pinned runtime dependency внутри
контейнера. Прежде чем выбирать способ запуска, выполнить spike:

1. GBrain PGLite на `/data`;
2. write/search/think round trip;
3. restart с сохранением данных;
4. последовательные writes из Telegram и API;
5. remote MCP client read/write;
6. reindex из Markdown после удаления тестового PGLite.

## 14. Конфигурация

Черновой полный набор переменных:

```text
TELEGRAM_BOT_TOKEN=
ALLOWED_TELEGRAM_USER_IDS=
ALLOWED_TELEGRAM_CHAT_IDS=

LIBRARY_DATA_ROOT=/data/library
LIBRARY_BRAIN_ROOT=/data/library/brain
LIBRARY_ATTACHMENTS_ROOT=/data/library/brain/attachments
LIBRARY_SQLITE_PATH=/data/library/library.sqlite3

LIBRARY_PUBLIC_URL=
LIBRARY_API_TOKEN=
MCP_AUTH_TOKEN=

LIBRARY_GBRAIN_COMMAND=gbrain
LIBRARY_GBRAIN_MODE=pglite
LIBRARY_GBRAIN_HOME=/data/library/gbrain
LIBRARY_GBRAIN_VERSION=
LIBRARY_GBRAIN_TIMEOUT_SECONDS=30

LIBRARIAN_LLM_BASE_URL=
LIBRARIAN_LLM_API_KEY=
LIBRARIAN_LLM_MODEL=
LIBRARIAN_LLM_TIMEOUT_SECONDS=60

LIBRARY_IMAGE_MAX_LONG_SIDE_PX=2048
LIBRARY_IMAGE_FORMAT=webp
LIBRARY_IMAGE_QUALITY=85
LIBRARY_KEEP_ORIGINALS=false
LIBRARY_IMAGE_VISION_ANALYSIS=false

LIBRARY_SCHEMA_MUTATION_MODE=propose
LIBRARY_INGEST_MAX_RETRIES=5
LIBRARY_MEDIA_GROUP_SETTLE_SECONDS=3
LIBRARY_JOB_POLL_SECONDS=1
LOG_LEVEL=INFO
```

Названия конкретных GBrain provider/model settings уточнить в bootstrap spike и
зафиксировать в `.env.example`. Не проксировать неизвестные переменные
пользовательского окружения в GBrain subprocess.

## 15. Railway deployment

### 15.1. Требования

- одна Railway service replica;
- persistent volume смонтирован в `/data`;
- healthcheck `/healthz`;
- readiness требует writable volume, SQLite и GBrain health;
- graceful shutdown завершает активную SQLite transaction и не начинает новый
  mutating GBrain job;
- deploy не обновляет GBrain без изменения pinned version в репозитории.

### 15.2. Backup

Резервировать:

```text
brain/
attachments/
library.sqlite3
```

PGLite также можно резервировать, но восстановление не должно от него зависеть.
Периодически проверять rebuild индекса из Markdown на чистом временном каталоге.

### 15.3. Наблюдаемость

Метрики/логи:

- ingest received/completed/failed;
- duplicate receipts;
- GBrain search/think latency;
- LLM calls and token usage;
- pending index jobs;
- attachment bytes;
- PGLite lock contention;
- schema proposals;
- Telegram delivery failures.

Не логировать bot/API tokens и содержимое приватных материалов на INFO level.

## 16. Этапы разработки

### Этап 0. Репозиторий и GBrain spike

- [ ] Создать новый репозиторий и Python package.
- [ ] Добавить CI, lint/type/test commands и Docker build.
- [ ] Закрепить GBrain version/commit.
- [ ] Проверить PGLite на persistent path.
- [ ] Проверить `put_page`, search и think.
- [ ] Проверить удалённый MCP-клиент с bearer token.
- [ ] Проверить полный rebuild из Markdown.
- [ ] Зафиксировать способ запуска GBrain в контейнере.

Критерий: после restart тестовая страница находится через search, а внешний MCP-клиент может
создать вторую страницу без Telegram.

### Этап 1. Storage core

- [ ] Реализовать Settings с fail-fast validation.
- [ ] Реализовать SQLite migrations и repository.
- [ ] Реализовать atomic Markdown writer.
- [ ] Реализовать attachment storage и image compression.
- [ ] Реализовать idempotency receipts.
- [ ] Реализовать serialized GBrain adapter.
- [ ] Добавить `research-v1` schema pack.

Критерий: typed item с двумя изображениями сохраняется повторяемо и находится
через GBrain после restart.

### Этап 2. REST API

- [ ] Реализовать health/readiness.
- [ ] Реализовать uploads.
- [ ] Реализовать items, experiment reports, ideas и publications.
- [ ] Реализовать search/ask.
- [ ] Реализовать bearer service tokens.
- [ ] Реализовать retryable jobs и status endpoint.
- [ ] Опубликовать OpenAPI schema.

Критерий: AutoResearch fixture создаёт отчёт и повторяет запрос без дубликата.

### Этап 3. Telegram ingestion

- [ ] Подключить aiogram polling.
- [ ] Реализовать allowlists.
- [ ] Обработать forwarded messages.
- [ ] Обработать media groups.
- [ ] Реализовать `/collect`, `/save`, `/cancel`.
- [ ] Реализовать commands для idea/publication.
- [ ] Реализовать понятные terminal receipts.

Критерий: forwarded report с несколькими изображениями становится одним item.

### Этап 4. Librarian query/enrichment

- [ ] Реализовать deterministic intent router.
- [ ] Добавить bounded LLM fallback.
- [ ] Подключить GBrain search и think.
- [ ] Добавить citations/source rendering.
- [ ] Добавить related items.
- [ ] Добавить dedup по URL/content similarity.
- [ ] Добавить schema proposal workflow.

Критерий: запрос по описанию находит отчёт без знания ID и возвращает исходные
изображения.

### Этап 5. Интеграция внешних исследовательских сервисов

- [ ] Реализовать MCP facade.
- [ ] Подключить MCP-клиент из отдельного репозитория.
- [ ] Добавить typed experiment report contract.
- [ ] Добавить multipart artifact upload.
- [ ] Подключить AutoResearch outbox publisher.
- [ ] Проверить retry после недоступности Library Service.
- [ ] Ограничить MCP tools read/write без schema admin/delete.

Критерий: завершённый эксперимент появляется в библиотеке без Telegram и
находится через библиотечного бота.

### Этап 6. Production hardening

- [ ] Railway volume/redeploy E2E.
- [ ] Backup и clean rebuild drill.
- [ ] Ограничение размеров payload/files.
- [ ] Timeout/retry/circuit breaker для GBrain и LLM.
- [ ] Recovery зависших ingestion jobs.
- [ ] Rate limits Telegram/API.
- [ ] Usage/cost counters.
- [ ] Operational runbook.

## 17. Тестирование

### Unit

- config validation;
- idempotency key and payload hash;
- Telegram intent classification;
- media group aggregation;
- Markdown/frontmatter generation;
- slug normalization;
- image resize/no-upscale;
- schema validation;
- retry state machine.

### Integration

- SQLite restart and migrations;
- atomic file failure recovery;
- real GBrain PGLite write/search;
- PGLite rebuild from Markdown;
- search vs think routing;
- attachment upload;
- schema pack validation;
- API token scopes.

### E2E

- forwarded Telegram report with one photo;
- forwarded album;
- `/collect` batch;
- duplicate Telegram update;
- idea and publication;
- natural-language lookup by description;
- direct experiment report from an external service;
- external service artifact upload;
- Library restart during indexing;
- GBrain temporarily unavailable;
- Railway volume restart;
- AutoResearch outbox retry.

## 18. Критерии готовности MVP

- Telegram-forward с изображениями сохраняется без экспорта истории и OCR.
- Идеи, публикации и отчёты получают разные page types.
- Поиск работает по описанию, а не только по ID.
- `/ask` формирует ответ с указанием страниц-источников.
- Внешний сервис сохраняет отчёт напрямую через API/MCP без Telegram.
- Повторный MCP/Telegram запрос не создаёт дубликат.
- Изображения сохраняются на volume с заданной длинной стороной.
- Restart/redeploy не теряет Markdown, attachments и ingestion receipts.
- Удаление PGLite не уничтожает знания; индекс перестраивается из Markdown.
- Библиотека не хранит authoritative experiment/checkpoint/resume state.
- AutoResearch продолжает работать при недоступной библиотеке и доставляет
  завершённый отчёт позже через outbox.

## 19. Не входит в MVP

- Obsidian и Obsidian Sync;
- OCR;
- автоматический анализ изображений;
- web UI;
- полноценный теоретический autorеsearch;
- управление RunPod;
- хранение training checkpoints;
- пошаговые training metrics;
- несколько Railway replicas;
- публичный доступ;
- автоматический массовый web crawling публикаций;
- автономные GBrain Minions/dream cycle.

## 20. Первый рабочий инкремент

Чтобы начать разработку без дополнительного проектирования, первая задача
нового репозитория:

1. поднять pinned GBrain + PGLite в Docker;
2. хранить brain/PGLite в `/data/library`;
3. реализовать `POST /v1/items`;
4. сформировать одну Markdown-страницу research-v1;
5. вызвать GBrain indexing;
6. реализовать `POST /v1/search`;
7. подключить один внешний MCP-клиент;
8. доказать write → restart → search;
9. только после этого добавлять Telegram и изображения.

Это проверяет самый рискованный архитектурный шов до разработки интерфейсов.
