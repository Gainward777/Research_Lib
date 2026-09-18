# План разделения доступа к разделам Research Library

## 1. Цель

Заменить два общих bearer-секрета моделью настоящей библиотеки с открытыми,
внутренними и закрытыми разделами, не вводя ACL для отдельных документов.

Система должна одновременно поддерживать:

- закрытые Memento-разделы проектов разработки;
- общую или закрытую исследовательскую базу;
- публикацию журналов экспериментов сервисом AutoResearch;
- отдельные токены разработчиков, агентов, CI и внешних сервисов;
- отзыв одного токена без перенастройки остальных клиентов.

## 2. Текущее состояние

REST проверяет один `LIBRARY_API_TOKEN`, MCP — один `MCP_AUTH_TOKEN`. После
успешной проверки клиент получает доступ ко всем операциям интерфейса.

Проблемы:

- нельзя определить конкретного клиента;
- нельзя ограничить токен разделом или только чтением;
- нельзя отозвать одного клиента;
- входной `project` выбирается самим клиентом;
- общий поиск может смешивать research и Memento;
- отсутствие настроенного токена открывает весь соответствующий интерфейс.

## 3. Основные решения

### 3.1. Раздел как граница доступа

Каждый материал относится ровно к одному `section`.

Раздел имеет:

- `domain`: `memento` или `research`;
- стабильный `key`;
- отображаемое название;
- политику чтения;
- состояние `active/archived`.

Примеры:

```text
memento/backend
memento/mobile
research/main
research/private-runs
```

Markdown, attachments и GBrain могут оставаться на одном Railway volume. Граница
доступа обеспечивается прикладным слоем и обязательной section-маркировкой данных
и индекса.

### 3.2. Политики чтения

| Политика | Кто может читать |
|---|---|
| `public` | анонимный клиент; включается только явно |
| `authenticated` | любой клиент с действующим токеном |
| `restricted` | только токен с явным grant раздела |

Запись и администрирование никогда не бывают публичными.

Начальная конфигурация:

- Memento-проекты — `restricted`;
- `research/main` — `restricted` по умолчанию; `authenticated` включается оператором явно;
- truly public sections выключены глобально до явного разрешения оператора.

### 3.3. Разрешения

- `read` — поиск, чтение материала и разрешённых связей;
- `publish` — `read` плюс создание материалов и вложений;
- `admin` — `publish` плюс управление конкретным разделом и его grants;
- `system_admin` — создание разделов и глобальные административные операции.

Section-level `admin` не даёт доступ к другим разделам, schema mutations GBrain
или глобальному удалению.

## 4. Субъекты и токены

Токен выдаётся конкретному субъекту: разработчику, агенту, CI, Telegram-боту,
AutoResearch outbox или другой интеграции. Один токен может иметь несколько grants,
но независимые сервисы всегда получают разные токены.

Примеры:

```text
developer-backend:
  memento/backend: read,publish
  research/main: read

autoresearch-outbox:
  research/main: read,publish

anonymous:
  только public sections
```

Токен имеет непрозрачный формат с минимум 256 битами энтропии:

```text
rl_<public-prefix>_<secret>
```

Библиотека генерирует токен, показывает его один раз и хранит только public prefix
и HMAC/hash. Исходный токен не попадает в SQLite, Markdown, GBrain или логи.
Для HMAC используется `LIBRARY_TOKEN_PEPPER` из Railway Variables.

## 5. Модель данных

Добавить миграцию
`src/controllers/utils/BD/migrations/versions/0002_access_sections.sql`.

### 5.1. `library_sections`

```text
id
domain                 memento | research
key
title
read_policy            public | authenticated | restricted
status                 active | archived
created_at
updated_at
UNIQUE(domain, key)
```

### 5.2. `access_tokens`

```text
id
name
public_prefix
token_hash
subject_type           developer | agent | ci | telegram | service
expires_at
revoked_at
last_used_at
created_by_token_id
created_at
```

### 5.3. `token_grants`

```text
token_id
section_id             NULL только для system_admin
permission             read | publish | admin | system_admin
created_at
PRIMARY KEY(token_id, section_id, permission)
```

Ограничения БД запрещают `system_admin` с конкретным section и обычный permission
без section.

### 5.4. `auth_audit_events`

Хранить административные события: создание/отзыв токена, изменение grants,
создание/архивацию раздела и смену read policy. Содержимое материалов и секреты в
audit не записываются.

### 5.5. Section-aware сущности

Добавить `section_id` в:

- `library_items`;
- `uploads`;
- `ingest_jobs`;
- `idempotency_receipts`.

Idempotency становится section-scoped. Одинаковый внешний ключ допустим в разных
разделах, но не внутри одного раздела. Upload можно присоединить только к материалу
того же section.

## 6. Авторизационный контекст

Добавить модели `AuthPrincipal`, `AuthGrant`, `AuthorizationContext`,
`LibrarySection` и `SectionRef`.

`AuthorizationContext` содержит:

- безопасный `principal_id`;
- anonymous/authenticated state;
- grants;
- разрешённые sections;
- признак legacy-аутентификации на время миграции.

Контроллеры не передают исходный bearer token в сервисы. Центральный
`AuthorizationService` реализует:

- `can_read(section)`;
- `require_publish(section)`;
- `require_admin(section)`;
- `resolve_readable_sections(filter)`;
- запрет делегировать права шире прав вызывающего администратора.

## 7. Правила операций

### 7.1. Memento

`project` отображается в `memento/<project>`.

- Публикация требует `publish` этого раздела.
- При одном доступном Memento-разделе project можно вывести из токена.
- При нескольких разделах project обязателен.
- Переданный project всегда проверяется по grants.
- Поиск без project выполняется только по разрешённым Memento-разделам.

### 7.2. Research и AutoResearch

Experiment reports, ideas, publications и другие исследовательские материалы
попадают в `research/<workspace>`.

- AutoResearch получает отдельный service token.
- `autoresearch-outbox` получает `research/main:read,publish`.
- Run/checkpoint/resume остаются в AutoResearch PostgreSQL.
- В Библиотеке остаются устойчивые отчёты, идеи, публикации и артефакты.
- Токен Memento-проекта не получает research-доступ автоматически.

### 7.3. Search и ask

`library_search` и `ask` работают только по sections, доступным principal.
Фильтрация выполняется до возврата текста и до передачи контекста LLM.

Запрещено:

- искать по всей базе с последующей фильтрацией;
- передавать LLM недоступные фрагменты;
- раскрывать ID, title, relations или количество закрытых материалов;
- принимать section из payload без проверки grants.

Если GBrain не поддерживает безопасный OR-фильтр для нескольких sections, поиск
выполняется отдельно по каждому разрешённому разделу с последующим объединением и
дедупликацией результатов.

### 7.4. Get, relations и attachments

- Section item проверяется до возврата данных.
- Для недоступного item возвращается `404`, чтобы не раскрывать существование.
- Недоступные targets полностью исключаются из relations.
- Cross-section relation требует `publish` на source и `read` на target.
- Скачать attachment можно только при наличии read-доступа к его section.

### 7.5. Public sections

- Запрос без токена получает principal `anonymous`.
- Anonymous может только читать/искать/задавать вопросы в `public` sections.
- Любая запись без токена возвращает `401`.
- Глобальный флаг аварийно отключает anonymous-доступ без изменения БД.

## 8. Изменения по папкам

```text
src/
├── models/
│   └── access.py
├── controllers/
│   ├── admin/
│   │   ├── section_controller.py
│   │   └── token_controller.py
│   ├── api/
│   │   └── auth.py
│   ├── mcp/
│   │   └── auth.py
│   └── utils/
│       ├── BD/
│       │   ├── access.py
│       │   ├── sections.py
│       │   └── migrations/versions/
│       │       └── 0002_access_sections.sql
│       ├── infrastructure/security/
│       │   └── token_hasher.py
│       ├── services/access/
│       │   ├── authorization_service.py
│       │   ├── section_service.py
│       │   └── token_service.py
│       └── bootstrap/
│           ├── dependencies.py
│           └── settings.py
```

`ItemService`, `SearchService`, `MementoService`, research services, upload и
ingestion получают section-aware контракты. REST и MCP используют одну прикладную
логику.

## 9. REST, MCP и управление

### 9.1. REST

`require_read` и `require_write` заменяются resolver-зависимостью, возвращающей
`AuthorizationContext`. Конкретный section проверяет сервисный слой.

HTTP-семантика:

- `401` — отсутствующий/невалидный обязательный токен;
- `403` — валидный токен без права публикации или администрирования;
- `404` — отсутствующий либо недоступный конкретный item.

### 9.2. MCP

MCP middleware валидирует bearer один раз и связывает `AuthorizationContext` с
request context. `dispatch` и MCP controllers используют этот контекст.
Существующие имена tools сохраняются, но становятся section-aware.

Управление токенами не публикуется как обычные MCP tools.

### 9.3. Администрирование

Первый `system_admin` создаётся CLI-командой внутри Railway container. Постоянный
root token в environment не требуется.

Минимальные команды:

```text
library-admin sections list|create|set-policy
library-admin tokens create|list|revoke
library-admin grants add|remove
```

После bootstrap допустим защищённый admin REST API:

```text
GET    /v1/admin/sections
POST   /v1/admin/sections
PATCH  /v1/admin/sections/{id}
GET    /v1/admin/tokens
POST   /v1/admin/tokens
DELETE /v1/admin/tokens/{id}
```

Section admin делегирует только свой section и только права, которыми обладает сам.
Исходный токен возвращается исключительно в ответе на create.

## 10. Markdown и GBrain

В frontmatter каждого материала добавить:

```yaml
section:
  domain: research
  key: main
```

При индексации обязателен нормализованный тег:

```text
section:research/main
section:memento/backend
```

GBrain adapter принимает обязательные section filters. Вызов search/think без них
разрешён только внутренней system-admin операции. Rebuild восстанавливает section
из frontmatter. Материал без section помещается в закрытый карантин.

## 11. Миграция данных

Перед миграцией создаётся backup Railway volume и SQLite.

Backfill:

1. `development-context` получает `memento/<metadata.project>`.
2. Остальные research types получают `research/main`.
3. Memento без project попадает в закрытый `memento/_unassigned`.
4. Section записывается в SQLite и Markdown frontmatter.
5. GBrain index полностью перестраивается.
6. Сверяются количество материалов и attachments до и после миграции.

Миграция повторяема. До успешного backfill приложение работает в
maintenance/read-only режиме, чтобы не возникли частично открытые данные.

## 12. Совместимость текущих токенов

`LIBRARY_API_TOKEN` и `MCP_AUTH_TOKEN` временно обслуживает compatibility
adapter, но grants задаются явно:

```text
LIBRARY_LEGACY_API_GRANTS=research/main:read,publish
LIBRARY_LEGACY_MCP_GRANTS=memento/backend:read,publish;research/main:read
```

Пустой список не означает полный доступ. Production запускается fail-closed, если
auth включён, но отсутствуют зарегистрированные токены и явный legacy mapping.

Переход:

1. Создать sections и выполнить backfill.
2. Выпустить отдельный AutoResearch token.
3. Выпустить developer/agent tokens.
4. Переключить клиентов и проверить audit/metrics.
5. Отозвать общие compatibility tokens.
6. Удалить legacy settings в следующем breaking release.

## 13. Railway Variables

```text
LIBRARY_AUTH_ENABLED=true
LIBRARY_TOKEN_PEPPER=<secret>
LIBRARY_PUBLIC_SECTIONS_ENABLED=false
LIBRARY_AUTH_FAIL_CLOSED=true

# Только на время миграции
LIBRARY_API_TOKEN=
MCP_AUTH_TOKEN=
LIBRARY_LEGACY_API_GRANTS=
LIBRARY_LEGACY_MCP_GRANTS=
```

Список новых токенов и hashes не хранится в environment.

## 14. Логи, метрики и аудит

В request context и JSON-логах допустимы `principal_id`, section domain/key,
`auth_outcome`, permission и `request_id`. Запрещены bearer, token hash,
Authorization header и содержимое материалов.

Метрики:

- auth success/failure;
- denied requests по operation/domain без token ID;
- active/revoked/expired token counts;
- запросы к public/authenticated/restricted sections;
- legacy-token usage.

`principal_id` остаётся только в Railway JSON logs и audit, а не в metric labels.

## 15. Этапы реализации

### Этап 1. Контракты и БД

- [x] Добавить enums/models section, principal, grant и permission.
- [x] Добавить migrations sections/tokens/grants/audit.
- [x] Добавить section_id к items, uploads, jobs и receipts.
- [x] Реализовать stores в `controllers/utils/BD`.
- [x] Добавить миграционные тесты.

### Этап 2. Ядро авторизации

- [x] Реализовать generation, hash, lookup, expiration и revoke токенов.
- [x] Реализовать `AuthorizationContext` и централизованную grant-проверку.
- [x] Реализовать permission inheritance и запрет privilege escalation.
- [x] Добавить fail-closed production mode.
- [x] Покрыть матрицу разрешений unit-тестами.

### Этап 3. Section-aware хранение

- [x] Сделать section обязательным для новых LibraryItem.
- [x] Привязать uploads, jobs и idempotency к section.
- [x] Добавить section во frontmatter и GBrain tags.
- [x] Сделать rebuild и retry section-aware.

### Этап 4. REST и MCP

- [x] Заменить общие token checks единым auth resolver.
- [x] Передавать auth context во все прикладные сервисы.
- [x] Ограничить get/search/ask/relations/attachments до возврата содержимого.
- [x] Проверять Memento project и research workspace по grants.
- [x] Сохранить внешние tool names и совместимые payload contracts.

### Этап 5. Управление

- [x] Добавить admin CLI для section/token/grant lifecycle.
- [x] Обеспечить one-time отображение токена.
- [x] Добавить audit административных действий.
- [x] Добавить защищённый admin REST API после CLI.
- [x] Проверить запрет расширения прав при делегировании.

### Этап 6. Backfill и rollout

- [x] Создать `research/main` и существующие Memento sections.
- [ ] Выполнить dry-run классификации материалов.
- [ ] Сделать backup и применить backfill.
- [x] Перестроить GBrain index.
- [ ] Выпустить AutoResearch и developer tokens.
- [x] Наблюдать legacy usage и auth denials.
- [ ] Отозвать compatibility tokens.

### Этап 7. Документация

- [x] Обновить README, `arch.md` и HTML-документацию.
- [x] Описать подключение AutoResearch outbox.
- [x] Описать Codex/Cursor/Claude Code без токена в репозитории.
- [x] Добавить runbook выдачи, ротации, отзыва и восстановления доступа.

## 15.1. Статус реализации

Программные этапы 1–5 и документация реализованы. Для backfill доступны команды
`library-admin migration dry-run|apply|verify`. Содержательный backfill не
выполняется автоматически: startup остаётся fail-closed, пока оператор не создаст
backup и явно не запустит `apply --backup-confirmed`. После завершённого backfill
новый Markdown без section помещается в закрытый `research/_quarantine`.
Операционные действия rollout — backup Railway volume, выполнение production
dry-run/backfill, выпуск production-токенов и отключение compatibility tokens —
остаются ручными и выполняются по `docs/access-rollout-runbook.md`.

## 16. Проверки

### Unit

- hash и constant-time validation;
- expiration/revoke;
- permission inheritance;
- public/authenticated/restricted policy;
- запрет выдать более широкий grant;
- нормализация section key;
- legacy grants parser.

### Integration

- REST и MCP используют одну authorization model;
- `memento/backend` не читает `memento/mobile`;
- Memento token без research grant не читает experiment reports;
- AutoResearch публикует в `research/main`, но не в Memento;
- authenticated reader читает общий research-раздел;
- anonymous читает только public sections;
- закрытый item по ID возвращает `404`;
- search/ask не передаёт закрытый контент GBrain/LLM;
- relation и attachment не обходят section boundary;
- revoked/expired token прекращает работать;
- idempotency изолирована между sections.

### Migration/E2E

- существующие experiment reports доступны AutoResearch;
- Memento-записи находятся только в своём проекте;
- restart/redeploy сохраняет grants;
- rebuild GBrain сохраняет section isolation;
- общий token отключается без остановки новых клиентов;
- параллельные разработчики не смешивают разделы.

## 17. Критерии готовности

1. Каждый материал имеет один section в SQLite, Markdown и GBrain.
2. AutoResearch сохраняет журналы отдельным service token.
3. Разработчик видит только разрешённые Memento и общие research sections.
4. Public section доступен без токена только при явном глобальном разрешении.
5. Невалидный, просроченный или отозванный токен не даёт доступа.
6. Search, ask, relations и attachments не раскрывают закрытые данные.
7. Токен показывается один раз; в хранилище остаётся только hash.
8. Отзыв одного токена не требует ротации остальных.
9. Audit устанавливает субъекта административного изменения.
10. Существующие тесты проходят вместе с новой auth-матрицей.

## 18. Не входит в первую версию

- ACL отдельных документов;
- пользовательские пароли;
- OAuth/OIDC/SSO;
- группы и вложенные роли;
- публичная запись;
- token management через Telegram или обычные MCP tools;
- перенос authoritative AutoResearch run state в Библиотеку.
