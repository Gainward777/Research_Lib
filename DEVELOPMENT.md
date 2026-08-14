# Запуск и разработка

## Локальная установка

Требования: Python 3.11–3.13 и `uv`.

```powershell
uv sync --dev
uv run uvicorn main:app --app-dir src --reload
```

API будет доступен на `http://127.0.0.1:8000`, OpenAPI — на `/docs`.

Файл `.env.example` содержит production-пути `/data`; для локального запуска он не обязателен.

По умолчанию данные записываются в `data/library`, а поиск работает в локальном
Markdown-режиме. Для GBrain установите pinned GBrain runtime, выполните `gbrain init`
для каталога из `LIBRARY_GBRAIN_HOME` и задайте:

```text
LIBRARY_GBRAIN_MODE=subprocess
LIBRARY_GBRAIN_COMMAND=gbrain
```

Subprocess получает только безопасный allowlist системных переменных окружения и
`GBRAIN_HOME`; неизвестные переменные и секреты ему не проксируются.

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

Если `LIBRARY_API_TOKEN` и `LIBRARY_CODEX_TOKEN` пусты, локальный API работает без
авторизации. В production хотя бы один токен должен быть задан.

## Telegram

Telegram polling запускается вместе с API, только если задан `TELEGRAM_BOT_TOKEN`.
Ограничьте доступ через `ALLOWED_TELEGRAM_USER_IDS` и
`ALLOWED_TELEGRAM_CHAT_IDS`.

## MCP

Локальный stdio server:

```powershell
$env:PYTHONPATH = 'src'
uv run python src/controllers/mcp/server.py
```

Streamable HTTP:

```powershell
$env:PYTHONPATH = 'src'
$env:LIBRARY_MCP_TRANSPORT = 'streamable-http'
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
