# Запуск и разработка

## Локальная установка

Для тестов нужны Python 3.11–3.13 и `uv`. Для запуска приложения обязателен также
GBrain `0.45.12.0`; production-образ собирает его автоматически.

```powershell
uv sync --dev
uv run pytest -q
```

Полный локальный запуск без установки GBrain на хост выполняется через Docker:

```powershell
docker build -t research-library .
docker run --rm -p 8000:8000 -v research-library-data:/data --env-file .env research-library
```

API будет доступен на `http://127.0.0.1:8000`, OpenAPI — на `/docs`. При запуске
на хосте `LIBRARY_GBRAIN_COMMAND` должен указывать на pinned GBrain CLI. Приложение
само инициализирует PGLite в `LIBRARY_GBRAIN_HOME`; Markdown-fallback отсутствует.
Subprocess получает системный allowlist, `GBRAIN_HOME` и только
`OPENAI_API_KEY`, но не Telegram/API/MCP tokens. Docker-образ применяет к pinned
GBrain репозиторный patch, который требует русский язык от `think`.

## Проверка
```powershell
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

## REST API

Создание материала:

```powershell
$headers = @{
  Authorization = 'Bearer dev-token'
  'Idempotency-Key' = 'manual:example:1'
}
$body = @{
  type = 'idea'
  title = 'Проверить новую гипотезу'
  content = 'Описание гипотезы'
  tags = @('example')
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/items -Headers $headers -ContentType application/json -Body $body
```

Если `LIBRARY_API_TOKEN` пуст, локальный REST API работает без авторизации.
Endpoint `/mcp` защищается отдельно через `MCP_AUTH_TOKEN`. В production задайте
оба токена, если REST API и MCP доступны по публичному домену.

## Telegram

Telegram polling запускается вместе с API, если заданы `TELEGRAM_BOT_TOKEN` и
`OPENAI_API_KEY`. Ограничьте доступ через `ALLOWED_TELEGRAM_USER_IDS` и
`ALLOWED_TELEGRAM_CHAT_IDS`. Роутер использует обычный OpenAI Responses API;
модель по умолчанию — `gpt-4.1-mini`, переопределение — `LIBRARY_ROUTER_MODEL`.
Все уточнения роутера и служебные сообщения формируются по-русски.

Естественный текст, forwarded messages, фото, documents и media groups проходят
через единый каталог скиллов. Неоднозначное намерение приводит к уточнению.
`/collect` и `/save` остаются алиасами естественных просьб начать и завершить сбор.

Ответ на русском генерирует GBrain с моделью
`LIBRARY_GBRAIN_THINK_MODEL=openai:gpt-4.1-mini`, а бот передаёт его текст без
изменений. Один `OPENAI_API_KEY` используется GBrain и роутером. Codex/MCP в
Telegram-роутере не используются.

## MCP

Streamable HTTP MCP запускается внутри основного FastAPI-процесса:

```powershell
$env:PYTHONPATH = 'src'
$env:MCP_AUTH_TOKEN = 'local-mcp-token'
uv run uvicorn main:app --app-dir src --reload
```

MCP-клиент подключается к `http://127.0.0.1:8000/mcp` с заголовком
`Authorization: Bearer local-mcp-token`.

Для локального stdio-подключения сервер можно запустить отдельно:

```powershell
$env:PYTHONPATH = 'src'
uv run python src/controllers/mcp/server.py
```
MCP tools:

- `library_search`;
- `library_get`;
- `library_get_related`;
- `library_save_experiment_report`;
- `library_save_idea`;
- `library_save_publication`.

## Эксплуатационные команды

```powershell
$env:PYTHONPATH = 'src'
uv run python scripts/bootstrap_gbrain.py
uv run python scripts/rebuild_index.py
uv run python scripts/backup.py --output backups
```

## Docker

```powershell
docker build -t research-library .
docker run --rm -p 8000:8000 -v research-library-data:/data --env-file .env research-library
```
