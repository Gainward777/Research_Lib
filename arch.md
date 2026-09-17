# Архитектурный план `research-library`

## 1. Назначение

`research-library` — самостоятельный сервис исследовательской библиотеки. Он принимает материалы из Telegram и внешних исследовательских сервисов, сохраняет устойчивые знания и позволяет искать их или задавать вопросы на естественном языке.

Сервис должен:

- принимать Telegram-сообщения, заметки, ссылки, публикации и изображения;
- принимать итоговые отчёты внешних сервисов через REST API или MCP;
- сохранять знания как Markdown-страницы с YAML frontmatter;
- хранить вложения на persistent volume;
- использовать GBrain с PGLite для полнотекстового, векторного и графового поиска;
- обеспечивать идемпотентность повторных запросов;
- переживать restart и redeploy без потери принятых материалов;
- позволять перестроить GBrain-индекс из Markdown;
- поддерживать последующую миграцию с PGLite на PostgreSQL без изменения внешнего API.

Сервис не управляет выполнением экспериментов. Runs, iterations, PID, checkpoints, quota pause и resume state принадлежат AutoResearch Control Plane. В библиотеку попадают только устойчивые результаты и знания.

## 2. Архитектурный стиль

Приложение строится на MVC:

- **Model** описывает библиотечные сущности, связи и доменные ограничения;
- **Controller** принимает REST, Telegram, MCP и фоновые события и управляет обработкой;
- **View** формирует JSON, Telegram-сообщения и MCP-результаты.

Все вспомогательные компоненты контроллеров располагаются в `controllers/utils`:

- `services` — прикладные сценарии контроллеров;
- `BD` — работа с Markdown, SQLite, вложениями и всеми миграциями;
- `infrastructure` — интеграции с GBrain, LLM, Telegram и файловой системой;
- `bootstrap` — конфигурация, создание зависимостей и жизненный цикл приложения.

## 3. Источники истины

```text
Markdown brain + attachments
    основной источник библиотечных знаний

GBrain PGLite
    производный индекс, embeddings и knowledge graph

SQLite
    служебное состояние ingestion, Telegram, uploads, retry и idempotency

AutoResearch PostgreSQL
    состояние выполнения экспериментов за пределами research-library
```

Основные правила:

- всё ценное должно быть записано в Markdown/frontmatter;
- PGLite считается перестраиваемым индексом;
- SQLite не дублирует содержимое Markdown-страниц;
- потеря PGLite не должна приводить к потере знаний;
- бинарные файлы не встраиваются в Markdown как base64;
- в MVP используется один writer и одна Railway replica.

## 4. Структура репозитория

```text
research-library/
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── errors.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── library_item.py
│   │   ├── experiment.py
│   │   ├── experiment_report.py
│   │   ├── idea.py
│   │   ├── publication.py
│   │   ├── attachment.py
│   │   ├── relation.py
│   │   ├── source.py
│   │   ├── ingest_job.py
│   │   ├── schema_proposal.py
│   │   └── enums.py
│   │
│   ├── controllers/
│   │   ├── __init__.py
│   │   ├── api/
│   │   │   ├── app.py
│   │   │   ├── auth.py
│   │   │   ├── requests.py
│   │   │   ├── health_controller.py
│   │   │   ├── upload_controller.py
│   │   │   ├── item_controller.py
│   │   │   ├── report_controller.py
│   │   │   ├── idea_controller.py
│   │   │   ├── publication_controller.py
│   │   │   ├── search_controller.py
│   │   │   ├── job_controller.py
│   │   │   └── schema_controller.py
│   │   │
│   │   ├── telegram/
│   │   │   ├── bot.py
│   │   │   ├── router.py
│   │   │   ├── action_controller.py
│   │   │   ├── message_controller.py
│   │   │   ├── command_controller.py
│   │   │   ├── extra_command_controller.py
│   │   │   ├── media_controller.py
│   │   │   └── media_group_controller.py
│   │   │
│   │   ├── mcp/
│   │   │   ├── server.py
│   │   │   ├── search_controller.py
│   │   │   ├── item_controller.py
│   │   │   └── save_controller.py
│   │   │
│   │   ├── workers/
│   │   │   ├── ingestion_controller.py
│   │   │   ├── retry_controller.py
│   │   │   └── reindex_controller.py
│   │   │
│   │   └── utils/
│   │       ├── services/
│   │       │   ├── ingestion/
│   │       │   │   ├── ingestion_service.py
│   │       │   │   ├── classifier.py
│   │       │   │   ├── idempotency_service.py
│   │       │   │   └── job_service.py
│   │       │   ├── library/
│   │       │   │   ├── item_service.py
│   │       │   │   ├── report_service.py
│   │       │   │   ├── idea_service.py
│   │       │   │   ├── publication_service.py
│   │       │   │   └── relation_service.py
│   │       │   ├── librarian/
│   │       │   │   ├── dialog_context.py
│   │       │   │   ├── enrichment_service.py
│   │       │   │   ├── search_service.py
│   │       │   │   └── answer_service.py
│   │       │   └── schema/
│   │       │       ├── validation_service.py
│   │       │       └── proposal_service.py
│   │       │
│   │       ├── BD/
│   │       │   ├── __init__.py
│   │       │   ├── markdown.py
│   │       │   ├── sqlite.py
│   │       │   ├── collections.py
│   │       │   ├── attachments.py
│   │       │   ├── receipts.py
│   │       │   ├── jobs.py
│   │       │   └── migrations/
│   │       │       ├── __init__.py
│   │       │       ├── runner.py
│   │       │       └── versions/
│   │       │           └── 0001_initial.sql
│   │       │
│   │       ├── infrastructure/
│   │       │   ├── gbrain/
│   │       │   │   ├── adapter.py
│   │       │   │   ├── process.py
│   │       │   │   ├── queue.py
│   │       │   │   └── schema_loader.py
│   │       │   ├── llm/
│   │       │   │   └── openai_responses.py
│   │       │   ├── telegram/
│   │       │   │   └── file_downloader.py
│   │       │   └── filesystem/
│   │       │       ├── atomic_writer.py
│   │       │       └── image_processor.py
│   │       │
│   │       ├── bootstrap/
│   │       │   ├── settings.py
│   │       │   ├── dependencies.py
│   │       │   └── lifecycle.py
│   │       ├── skills/
│   │       │   ├── models.py
│   │       │   ├── registry.py
│   │       │   ├── router.py
│   │       │   └── library.py
│   │       └── schema-packs/
│   │           └── research-v1/
│   │               ├── schema.yaml
│   │               ├── relations.yaml
│   │               └── templates/
│   │
│   └── views/
│       ├── api/
│       │   ├── responses.py
│       │   ├── item_view.py
│       │   ├── search_view.py
│       │   ├── job_view.py
│       │   └── error_view.py
│       ├── telegram/
│       │   ├── receipt_view.py
│       │   ├── item_view.py
│       │   ├── search_view.py
│       │   ├── answer_view.py
│       │   └── error_view.py
│       ├── mcp/
│       │   ├── item_view.py
│       │   ├── search_view.py
│       │   └── error_view.py

│
├── scripts/
│   ├── bootstrap_gbrain.py
│   ├── rebuild_index.py
│   └── backup.py
│
├── tests/
│   ├── unit/
│   │   ├── models/
│   │   ├── controllers/
│   │   ├── services/
│   │   ├── BD/
│   │   └── views/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/
│
├── Dockerfile
├── pyproject.toml
├── uv.lock
├── .env.example
├── AGENTS.md
├── README.md
└── arch.md
```

## 5. Назначение основных папок

### 5.1. `models`

Model содержит структуру и правила предметной области:

- библиотечные материалы;
- отчёты экспериментов;
- идеи и публикации;
- вложения и источники;
- связи между материалами;
- статусы ingestion jobs;
- schema proposals.

Модели не должны зависеть от FastAPI, aiogram, MCP, SQLite, файловой системы или GBrain.

Основные типы страниц:

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

Основные связи:

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

### 5.2. `controllers`

Controller принимает внешнее событие, валидирует транспортную часть, вызывает нужную утилиту и передаёт результат во View.

Контроллер не должен самостоятельно:

- записывать Markdown;
- выполнять SQL-запросы;
- обрабатывать изображения;
- реализовывать retry;
- индексировать данные;
- формировать итоговый текст ответа.

#### `controllers/api`

FastAPI controllers для REST endpoints, авторизации и преобразования HTTP request в команду приложения.

#### `controllers/telegram`

Обработка Telegram updates, команд, forwarded messages, media groups и сессий `/collect`.

#### `controllers/mcp`

Внешние MCP tools для независимых исследовательских сервисов.

#### `controllers/workers`

Контроллеры фоновых событий: ingestion, retry, pending indexing и полный reindex.

### 5.3. `controllers/utils/services`

Сервисы содержат сценарии, которые используют контроллеры:

- создание и получение материалов;
- сохранение отчёта эксперимента;
- классификация входного материала;
- enrichment;
- поиск и синтез ответа;
- управление relations;
- идемпотентность;
- retry и jobs;
- schema proposals.

Один сценарий должен быть общим для REST, Telegram и MCP. Различается только входной Controller и выходной View.

### 5.4. `controllers/utils/skills`

Зарегистрированные прикладные скиллы являются единственной точкой выполнения
пользовательских действий Telegram. Минимальный каталог:

- `ask_library`, `search_library`, `save_material`;
- `collect_material`, `append_collection`, `finish_collection`, `cancel_collection`;
- скиллы чтения item/relations/recent, schema proposals и health.

`router.py` получает исходный текст, метаданные вложений и Telegram, контекст
диалога и состояние collection. Он возвращает только строгий выбор скилла и
аргументы либо вопрос для уточнения. Роутер не отвечает пользователю, не вызывает
GBrain и не сохраняет материалы.

### 5.5. `controllers/utils/BD`

`BD` отвечает за постоянное и операционное хранение:

- `markdown.py` — запись и чтение Markdown/frontmatter;
- `sqlite.py` — подключение к SQLite и транзакции;
- `attachments.py` — хранение вложений;
- `receipts.py` — idempotency receipts и payload hashes;
- `jobs.py` — состояние ingestion и retry;
- `collections.py` — состояние составного Telegram-материала;
- `migrations/` — все миграции и механизм их применения.

Никакие миграции не размещаются вне `controllers/utils/BD/migrations`.

Требования к миграциям:

- последовательная нумерация;
- применение внутри транзакции, где это возможно;
- таблица установленной версии;
- безопасный повторный запуск;
- выполнение до запуска API, Telegram и workers;
- тестирование upgrade с предыдущей версии.

SQLite operational schema включает:

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

SQLite работает в WAL mode через одну async write queue.

### 5.6. `controllers/utils/infrastructure`

Infrastructure содержит адаптеры конкретных внешних технологий:

- управление GBrain subprocess;
- сериализованная очередь mutating-операций GBrain;
- вызовы GBrain `search`, `query` и `think`;
- обычный OpenAI Responses API-вызов со Structured Outputs только для выбора
  прикладного скилла;
- скачивание Telegram-файлов;
- atomic file writer;
- сжатие и нормализация изображений.

### 5.7. `controllers/utils/bootstrap`

Bootstrap подготавливает приложение к работе:

1. читает и валидирует настройки;
2. создаёт необходимые каталоги;
3. подключает SQLite;
4. применяет миграции из `BD/migrations`;
5. запускает GBrain;
6. создаёт services, каталог скиллов и LLM-роутер и передаёт им зависимости;
7. запускает REST API, Telegram polling и workers;
8. выполняет graceful shutdown.

### 5.8. `controllers/utils/schema-packs`

Schema packs содержат декларативные типы, связи, правила валидации и шаблоны Markdown-страниц для GBrain. Начальная схема хранится в `controllers/utils/schema-packs/research-v1`.

### 5.9. `views`

View преобразует готовый результат в формат конкретного интерфейса:

- `views/api` — JSON response models;
- `views/telegram` — текст, кнопки и сообщения Telegram;
- `views/mcp` — структурированный результат MCP tools.
- Клиентские интеграции находятся в репозиториях соответствующих MCP-клиентов.

View не обращается к BD, GBrain или LLM и не меняет модели.

## 6. Правила зависимостей

```text
Controller
    ├── Model
    ├── controllers/utils
    └── View

controllers/utils/services
    ├── Model
    ├── BD
    └── infrastructure

BD
    └── Model

infrastructure
    └── Model

View
    └── Model или готовый service result

Model
    └── не зависит от остальных слоёв
```

Запрещённые зависимости:

- Model не импортирует Controller или View;
- View не вызывает Controller;
- View не работает с BD;
- API, Telegram и MCP controllers не дублируют прикладную логику;
- BD не формирует пользовательские ответы;
- GBrain adapter не принимает транспортные HTTP или Telegram DTO.

## 7. Общий поток обработки

```text
REST / Telegram / MCP / Worker event
                |
                v
            Controller
                |
                v
    controllers/utils/services
          |             |
          v             v
       Model       BD / infrastructure
          |             |
          +------ result+
                |
                v
              View
                |
                v
     JSON / Telegram / MCP result
```

## 8. Ingestion pipeline

Состояния задания:

```text
received
  -> downloading
  -> stored_raw
  -> classifying
  -> writing_page
  -> indexing
  -> completed

Любой этап
  -> retryable_failed
  -> permanently_failed
```

Последовательность обработки:

1. Controller принимает сообщение или запрос.
2. `idempotency_service` проверяет ключ и payload hash.
3. Исходный текст и receipt фиксируются в SQLite.
4. Вложения скачиваются во временные файлы.
5. Материал классифицируется консервативными детерминированными правилами.
6. Создаётся Model библиотечного материала.
7. Вложения записываются атомарно.
8. Markdown/frontmatter записывается через temporary file и atomic rename.
9. Только после durable Markdown запускается индексация GBrain.
10. При ошибке GBrain материал сохраняется, а job переходит в `pending_index` или `retryable_failed`.
11. View сообщает terminal result или понятную ошибку.

## 9. Markdown brain

Runtime-структура знаний:

```text
/data/library/brain/
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
- дополнительные измерения задаются tags, properties и relations;
- сомнительный материал помещается в `inbox`;
- исходный Telegram-текст сохраняется без перезаписи;
- стабильный `library_item_id` хранится во frontmatter;
- slug является техническим путём, а не пользовательским ID;
- перемещение страницы не меняет `library_item_id`;
- длинные массивы метрик не помещаются во frontmatter.

Базовый frontmatter:

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

## 10. Вложения и изображения

Путь хранения:

```text
attachments/<library_item_id>/<sha256-prefix>-<safe-name>.<ext>
```

Pipeline изображения:

1. скачать максимальную доступную версию;
2. проверить MIME и размер;
3. применить ориентацию;
4. не увеличивать изображение;
5. уменьшить по длинной стороне;
6. преобразовать в настроенный формат;
7. вычислить SHA-256;
8. записать временный файл;
9. выполнить atomic rename;
10. связать attachment с library item.

В MVP OCR и автоматический vision-анализ отключены.

## 11. GBrain

GBrain используется как производный поисковый слой:

- `search` — retrieval без LLM-синтеза;
- `query` — расширенный retrieval без синтеза;
- `think` — LLM-синтез ответа с источниками;
- PGLite хранится на persistent volume;
- версия или commit GBrain закрепляется в репозитории;
- все mutating-операции проходят через одну очередь;
- индекс должен полностью перестраиваться из Markdown;
- raw GBrain MCP остаётся административным интерфейсом.

## 12. REST API

Версия API начинается с `/v1`:

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

Все mutating service-to-service endpoints требуют `Idempotency-Key`.

## 13. Telegram

Поддерживаются:

- forwarded message с caption и изображениями;
- media group по `media_group_id`;
- `/collect` → `/save`, включая текст, фото и документы;
- `/idea <text>`;
- `/paper <url-or-text>`;
- `/save <text>`;
- обычные сообщения и изображения;
- повтор update без создания дубликата.

Запросы:

```text
/search <query>
/ask <question>
/recent [type]
/item <id-or-slug>
/related <id-or-slug>
/collect
/save
/cancel
/schema
/health
```

Все команды являются необязательными алиасами зарегистрированных скиллов. Обычный
текст, caption, forwarded message, фото, документ и собранный album передаются в
LLM-роутер вместе с Telegram-метаданными и контекстом диалога.

Правила выполнения:

- обычный вопрос и `/ask` вызывают один `ask_library`;
- `ask_library` передаёт GBrain исходный вопрос, а ответ GBrain отправляется без
  дополнений, источников, перевода и переформатирования; допустимо только точное
  разбиение по лимиту Telegram;
- русский язык ответа задаётся внутри GBrain его build-патчем, поэтому passthrough
  не нарушается;
- любой отчёт, пересланный или написанный боту напрямую, сохраняется только через
  `save_material`, включая текст, фотографии, albums и документы;
- `collect_material` начинает накопление, `append_collection` добавляет очередное
  сообщение, `finish_collection` вызывает `save_material` один раз для всего набора;
- естественные фразы начала и завершения collection равноправны slash-алиасам;
- при неоднозначном намерении возвращается уточняющий вопрос на русском языке без
  поиска и записи.

Модель роутера по умолчанию — `gpt-4.1-mini`. Это отдельный обычный OpenAI API-вызов,
не Codex и не MCP. MCP подключается к библиотеке только как внешний интерфейс.

## 14. MCP

MCP-сервер является частью `Research_Lib` и публикуется основным FastAPI-процессом
по `/mcp` через Streamable HTTP. Другие репозитории содержат только MCP-клиенты.

Внешние MCP tools:

```text
library_search
library_get
library_get_related
library_save_experiment_report
library_save_idea
library_save_publication
```

Доступ защищается нейтральным `MCP_AUTH_TOKEN`. Административное применение
schema mutations, удаление страниц и внутренний GBrain adapter наружу не
публикуются. Клиент отвечает за retry с тем же idempotency key и не отправляет
secrets, checkpoints, полные логи или внутреннее состояние эксперимента.
## 15. Идемпотентность

Форматы ключей:

```text
Telegram message:
telegram:<chat_id>:<message_id>

Telegram media group:
telegram-group:<chat_id>:<media_group_id>

AutoResearch report:
autoresearch:<experiment_id>:<iteration_id>:<report_version>
```

Правила:

- повтор с тем же ключом и payload возвращает прежний результат;
- тот же ключ с другим payload возвращает conflict;
- retry не создаёт второй library item;
- payload hash и terminal response сохраняются в SQLite.

## 16. Research schema

Используется schema pack `research-v1`.

Режим изменения схемы:

```text
LIBRARY_SCHEMA_MUTATION_MODE=propose
```

В режиме `propose`:

- tags, relations и aliases могут создаваться автоматически;
- новые page types и relation types оформляются как proposal;
- proposal сохраняется в SQLite и показывается администратору;
- применение выполняется отдельной командой;
- каждая mutation версионируется и должна быть обратимой.

## 17. Runtime-структура

```text
/data/library/
├── brain/
│   ├── ... Markdown pages
│   └── attachments/
├── gbrain/
│   └── ... PGLite и служебные данные GBrain
└── library.sqlite3
```

| Данные | Назначение | Перестраиваются |
|---|---|---:|
| `brain/` | Основные знания | Нет |
| `brain/attachments/` | Изображения и артефакты | Нет |
| `gbrain/` | Индекс, embeddings и граф | Да |
| `library.sqlite3` | Jobs, sessions, receipts и retry | Частично |

## 18. Конфигурация

Основные переменные окружения:

```text
TELEGRAM_BOT_TOKEN=
ALLOWED_TELEGRAM_USER_IDS=
ALLOWED_TELEGRAM_CHAT_IDS=
OPENAI_API_KEY=
LIBRARY_ROUTER_MODEL=gpt-4.1-mini
LIBRARY_ROUTER_TIMEOUT_SECONDS=30
LIBRARY_ROUTER_CONTEXT_TURNS=12


LIBRARY_DATA_ROOT=/data/library
LIBRARY_BRAIN_ROOT=/data/library/brain
LIBRARY_ATTACHMENTS_ROOT=/data/library/brain/attachments
LIBRARY_SQLITE_PATH=/data/library/library.sqlite3

LIBRARY_PUBLIC_URL=
LIBRARY_API_TOKEN=
MCP_AUTH_TOKEN=

LIBRARY_GBRAIN_COMMAND=gbrain
LIBRARY_GBRAIN_HOME=/data/library/gbrain
LIBRARY_GBRAIN_VERSION=0.45.12.0
LIBRARY_GBRAIN_TIMEOUT_SECONDS=120
LIBRARY_GBRAIN_NO_EMBEDDING=true
LIBRARY_GBRAIN_EMBEDDING_MODEL=
LIBRARY_GBRAIN_EMBEDDING_DIMENSIONS=
LIBRARY_GBRAIN_THINK_MODEL=openai:gpt-4.1-mini

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

`OPENAI_API_KEY` обязателен при включённом Telegram и используется LLM-роутером
через Responses API и GBrain `think`. `LIBRARY_ROUTER_MODEL` по умолчанию равен
`gpt-4.1-mini`, а `LIBRARY_GBRAIN_THINK_MODEL` — `openai:gpt-4.1-mini`. Эти вызовы
не запускают Codex и не используют MCP.

Единственный разрешённый LLM-провайдер — OpenAI. GBrain subprocess получает только
`OPENAI_API_KEY`; ключи других провайдеров и неизвестные переменные окружения ему
не передаются.

## 19. Безопасность

- Telegram ограничивается allowlist пользователей и чатов;
- REST и MCP используют bearer service tokens;
- MCP-клиент получает только необходимые read/write scopes;
- schema admin и delete недоступны обычному MCP token;
- bot/API tokens не записываются в SQLite и логи;
- содержимое приватных материалов не логируется на INFO level;
- MIME определяется по содержимому файла;
- имена вложений нормализуются;
- размеры request, upload и изображения ограничиваются.

## 20. Railway deployment

Требования:

- одна Railway service replica;
- persistent volume смонтирован в `/data`;
- `/healthz` проверяет процесс;
- `/readyz` проверяет writable volume, SQLite migrations и GBrain;
- graceful shutdown завершает активную SQLite transaction;
- во время shutdown не запускаются новые mutating GBrain jobs;
- GBrain 0.45.12.0 собирается из commit
  `7fdcd8bd2ee0b3546b167da14cddd27eb2507212`, затем получает локальный patch
  `scripts/gbrain-russian-output.patch`; версия и patch не меняются без явного
  изменения репозитория.

Резервировать обязательно:

```text
brain/
brain/attachments/
library.sqlite3
```

PGLite можно резервировать дополнительно, но восстановление не должно от него зависеть. Периодически выполняется проверочный rebuild на чистом временном каталоге.

## 21. Наблюдаемость

Метрики и события:

- ingest received/completed/failed;
- duplicate receipts;
- GBrain search/think latency;
- LLM calls и token usage;
- pending index jobs;
- attachment bytes;
- PGLite lock contention;
- schema proposals;
- Telegram delivery failures;
- migration version и migration failures.

## 22. Тестирование

### Unit

- Model validation;
- idempotency key и payload hash;
- строгий контракт LLM-роутера и clarification;
- регистрация и аргументы Telegram-скиллов;
- media group aggregation;
- Markdown/frontmatter generation;
- slug normalization;
- image resize без upscale;
- schema validation;
- retry state machine;
- View rendering;
- Controller-to-skill mapping;
- точное сохранение всех символов GBrain-ответа при Telegram splitting.

### Integration

- применение SQLite migrations;
- SQLite restart и WAL;
- atomic file failure recovery;
- реальный GBrain PGLite write/search;
- rebuild PGLite из Markdown;
- search и think routing;
- attachment upload;
- schema pack validation;
- API token scopes.

### E2E

- forwarded Telegram report с фотографией;
- forwarded album;
- `/collect` batch;
- duplicate Telegram update;
- идея и публикация;
- поиск по описанию;
- direct experiment report from an external service;
- external service artifact upload;
- restart во время indexing;
- временная недоступность GBrain;
- Railway volume restart;
- AutoResearch outbox retry.

## 23. Этапы разработки

### Этап 0. Bootstrap и GBrain spike

- создать Python package и базовые MVC-папки;
- добавить Docker build, lint и tests;
- закрепить GBrain version/commit;
- проверить PGLite на persistent path;
- проверить write/search/think;
- проверить restart и rebuild из Markdown;
- проверить внешний MCP client read/write.

### Этап 1. Model и BD

- реализовать основные Models;
- реализовать настройки bootstrap;
- создать SQLite migration runner;
- добавить начальную миграцию;
- реализовать Markdown writer;
- реализовать attachments;
- реализовать idempotency receipts;
- добавить `research-v1`.

### Этап 2. API MVC

- реализовать API Controllers;
- реализовать JSON Views;
- реализовать uploads, items и reports;
- реализовать search и ask;
- добавить auth и OpenAPI;
- реализовать jobs endpoint.

### Этап 3. Telegram MVC

- подключить aiogram polling;
- реализовать Telegram Controllers;
- реализовать Telegram Views;
- добавить allowlists;
- обработать forwarded messages и media groups;
- реализовать `/collect`, `/save`, `/cancel`.

### Этап 4. Librarian

- LLM-роутер и каталог прикладных скиллов реализованы;
- GBrain search/think и точный passthrough ответа реализованы;
- related items и schema proposal workflow реализованы;
- dedup по URL/content similarity остаётся следующим этапом.

### Этап 5. Внешние исследовательские сервисы

- реализовать MCP Controllers и Views;
- подключить MCP-клиент из отдельного репозитория;
- добавить typed experiment report;
- добавить multipart artifact upload;
- подключить durable AutoResearch outbox;
- проверить retry без дубликатов.

### Этап 6. Production hardening

- Railway restart/redeploy E2E;
- backup и clean rebuild drill;
- rate limits и size limits;
- timeout, retry и circuit breaker;
- recovery зависших jobs;
- usage/cost counters;
- operational runbook.

## 24. Критерии готовности MVP

- Telegram-forward с изображениями сохраняется без OCR;
- идеи, публикации и отчёты получают разные page types;
- поиск работает по описанию, а не только по ID;
- `/ask` и естественный вопрос возвращают неизменённый текст ответа GBrain;
- Внешний сервис сохраняет отчёт через API/MCP без Telegram;
- повторный запрос не создаёт дубликат;
- restart/redeploy не теряет Markdown, attachments и receipts;
- удаление PGLite не уничтожает знания;
- GBrain-индекс перестраивается из Markdown;
- библиотека не хранит authoritative experiment state;
- AutoResearch продолжает работать при недоступной библиотеке и доставляет отчёт позже.

## 25. Не входит в MVP

- Obsidian и Obsidian Sync;
- OCR;
- автоматический анализ изображений;
- web UI;
- управление RunPod;
- хранение checkpoints;
- пошаговые training metrics;
- несколько Railway replicas;
- публичный доступ;
- массовый web crawling;
- автономные GBrain Minions и dream cycle.

## 26. Первый рабочий инкремент

1. Создать MVC-каркас.
2. Поднять pinned GBrain и PGLite в Docker.
3. Реализовать Model `LibraryItem`.
4. Реализовать `BD/migrations` и начальную SQLite-схему.
5. Реализовать Markdown storage в `controllers/utils/BD`.
6. Реализовать `POST /v1/items` через Controller, service и View.
7. Индексировать созданную страницу в GBrain.
8. Реализовать `POST /v1/search`.
9. Подключить один внешний MCP client.
10. Доказать сценарий write → restart → search.
11. Только после этого добавлять Telegram и обработку изображений.

Этот инкремент проверяет самый рискованный архитектурный шов: сохранение знания как Markdown, восстановление после restart и перестраиваемую индексацию GBrain.
