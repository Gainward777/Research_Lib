# Разделы и project-scoped токены

## Назначение

Каждый материал Research Library принадлежит одному разделу:

- `memento/<project>` — история разработки конкретного проекта;
- `research/<workspace>` — исследовательские материалы и отчёты.

Токен выдаётся конкретному разработчику, агенту, CI или сервису. Исходный токен
показывается один раз. В SQLite сохраняются только public prefix и HMAC-SHA256,
вычисленный с `LIBRARY_TOKEN_PEPPER`.

Разрешения наследуются:

`admin → publish → read`.

`system_admin` не привязан к разделу. Управление токенами не публикуется через
обычные MCP tools.

## Railway Variables

Для включения новой модели доступа:

```text
LIBRARY_AUTH_ENABLED=true
LIBRARY_TOKEN_PEPPER=<отдельный длинный случайный секрет>
LIBRARY_PUBLIC_SECTIONS_ENABLED=false
LIBRARY_AUTH_FAIL_CLOSED=true
```

`LIBRARY_TOKEN_PEPPER` нельзя менять без плановой перевыдачи всех токенов:
изменение pepper делает существующие hashes непроверяемыми.

Общие токены допускаются только на время перехода:

```text
LIBRARY_API_TOKEN=<старый REST token>
MCP_AUTH_TOKEN=<старый MCP token>
LIBRARY_LEGACY_API_GRANTS=research/main:read,publish
LIBRARY_LEGACY_MCP_GRANTS=memento/backend:read,publish;research/main:read
```

Пустой legacy mapping не предоставляет полный доступ. После миграции старые
токены следует очистить в Railway Variables.

## Первичный bootstrap

Перед первым production-запуском сделайте backup Railway volume. После запуска
миграции откройте Railway shell и создайте первый `system_admin`:

```bash
uv run library-admin tokens bootstrap --name platform-admin
```

Команда сработает только пока в БД нет ни одного access token. Поле `token` из
ответа сохраните в password manager. Повторно получить его из Библиотеки нельзя.

Создайте разделы:

```bash
uv run library-admin --token "$ADMIN_TOKEN" sections create memento/backend \
  --title "Backend development memory" --policy restricted

uv run library-admin --token "$ADMIN_TOKEN" sections create research/private-runs \
  --title "Private research runs" --policy restricted
```

`research/main` и закрытый карантин `memento/_unassigned` создаются миграцией.

## Выдача токенов

AutoResearch:

```bash
uv run library-admin --token "$ADMIN_TOKEN" tokens create \
  --name autoresearch-outbox --subject-type service \
  --grant research/main:read,publish
```

Агент backend-разработчика:

```bash
uv run library-admin --token "$ADMIN_TOKEN" tokens create \
  --name backend-agent --subject-type agent \
  --grant memento/backend:read,publish \
  --grant research/main:read
```

Встроенный Telegram-бот получает отдельный `telegram` token с нужным research grant. Его
исходное значение хранится в Railway secret `LIBRARY_TELEGRAM_ACCESS_TOKEN`.

```bash
uv run library-admin --token "$ADMIN_TOKEN" tokens create \\
  --name telegram-librarian --subject-type telegram \\
  --grant research/main:read,publish
```

После выдачи добавьте показанный `rl_...` token в Railway Variables.

CI с публикацией evidence:

```bash
uv run library-admin --token "$ADMIN_TOKEN" tokens create \
  --name backend-ci --subject-type ci \
  --grant memento/backend:read,publish
```

Токены нельзя сохранять в репозитории, Markdown или agent skill. Codex, Cursor и
Claude Code получают токен через локальную переменную окружения, secret manager
или настройку MCP-клиента.

## Использование REST и MCP

Один и тот же project-scoped bearer проверяется общей моделью как в REST, так и
на `/mcp`:

```http
Authorization: Bearer rl_<prefix>_<secret>
```

REST принимает optional section:

```json
{
  "section": {"domain": "research", "key": "main"},
  "type": "idea",
  "title": "Новая гипотеза",
  "content": "..."
}
```

Если токен имеет ровно один подходящий publish-раздел, section можно не
передавать. При неоднозначности он обязателен. Upload создаётся с query parameter:

```text
POST /v1/uploads?section=research/main
```

MCP tool `library_search` принимает необязательный массив:

```json
{"query": "refresh token bug", "sections": ["memento/backend"]}
```

Search выполняется отдельно по разрешённым GBrain sources и объединяет результаты.
Ask требует один явно выбранный или единственный доступный раздел, чтобы
недоступный контекст никогда не передавался GBrain `think`.

## Политики чтения

- `public` — анонимное чтение только при
  `LIBRARY_PUBLIC_SECTIONS_ENABLED=true`;
- `authenticated` — чтение любым действующим project token;
- `restricted` — только явный `read`, `publish` или `admin` grant.

Запись всегда требует `publish`. Недоступный item возвращается как `404`,
чтобы не раскрывать его существование. Cross-section relation требует publish к
source и read к target. Upload невозможно присоединить к другому section.

## Ротация и отзыв

Создайте новый токен, переключите клиента и только после проверки отзовите старый:

```bash
uv run library-admin --token "$ADMIN_TOKEN" tokens revoke tok_...
```

Просмотр метаданных не показывает hash или исходный token:

```bash
uv run library-admin --token "$ADMIN_TOKEN" tokens list
```

Если утрачены все `system_admin` токены, автоматического bypass нет. Восстановите
SQLite из backup либо выполните проверенную оператором процедуру восстановления
БД в закрытом Railway shell. Это намеренно не является HTTP/MCP-функцией.

## Rollout существующих данных

При первом запуске миграция и rebuild выполняют backfill:

1. обычные материалы получают `research/main`;
2. `development-context` получает `memento/<metadata.project>`;
3. записи без project попадают в `memento/_unassigned`;
4. section записывается в SQLite, Markdown frontmatter и tag;
5. attachments, pending jobs и receipts перепривязываются к section материала;
6. GBrain индекс перестраивается в non-federated source на каждый section.

Перед rollout обязательно сохраните копию всего `/data/library`. После запуска
сверьте количество Markdown-страниц и строк `library_items`, проверьте поиск
двумя токенами разных проектов, затем отключите compatibility tokens.

## Аудит и метрики

`auth_audit_events` фиксирует создание/отзыв токена, grants и изменение sections
без содержимого материалов и секретов.

Метрики содержат только bounded labels:

- auth outcome, surface и legacy-флаг;
- denial operation/domain;
- public/authenticated/restricted read checks;
- active/revoked/expired token counts.

`principal_id` может присутствовать в JSON-логах, но никогда не является metric
label.
