# Runbook включения section-доступа в Railway

Этот runbook переводит production с общих `LIBRARY_API_TOKEN` и
`MCP_AUTH_TOKEN` на индивидуальные токены. Сейчас подключён только Telegram-бот,
поэтому создаётся один рабочий токен для `research/main`. Токены будущих агентов,
AutoResearch и разработчиков выпускаются позже теми же командами.

## 1. Предварительные условия

1. Выполняйте команды в Railway Terminal сервиса `Research_Lib` в окружении
   `production`.
2. Не отправляйте боту новые материалы до завершения backup и backfill.
3. Не сохраняйте выданные токены в репозитории, Markdown, issue или обычном логе.
4. Сохраните административный токен в password manager: повторно он не выводится.

## 2. Backup Railway volume

На локальной машине проверьте выбранный проект и volume:

```powershell
railway status
railway volume list --json
```

Если Railway CLI сообщает, что SSH key не зарегистрирован:

```powershell
railway ssh keys add
railway ssh keys list
```

Скачайте весь volume в каталог вне репозитория:

```powershell
$volumeId = "<volume-id из railway volume list>"
$backupDir = "C:\Backups\research-library-pre-auth-$(Get-Date -Format yyyyMMdd-HHmmss)"
New-Item -ItemType Directory -Path $backupDir
railway volume files --volume $volumeId download / $backupDir
```

Проверьте, что в backup присутствуют как минимум:

```text
library/library.sqlite3
library/brain/
library/gbrain/
```

Храните вместе с SQLite также `library.sqlite3-wal` и `library.sqlite3-shm`, если
они присутствуют. После завершения можно удалить временно добавленный SSH key:

```powershell
railway ssh keys remove
```

## 3. Dry-run и backfill

После развертывания версии с migration CLI откройте Railway Terminal и выполните:

```bash
uv run library-admin migration dry-run
```

Проверьте поля:

- `ok: true`;
- `errors: []`;
- `targets` соответствует ожидаемым Memento-проектам и `research/main`;
- материалы без корректного проекта направляются в `memento/_unassigned`.

Если `missing_section` больше нуля, примените backfill только после проверки
backup:

```bash
uv run library-admin migration apply --backup-confirmed
```

Затем выполните обязательную проверку:

```bash
uv run library-admin migration verify
```

Команда должна вернуть `ok: true`. Ненулевой `quarantined_items` не открывает
данные, но требует ручной классификации: карантин `research/_quarantine` всегда
имеет политику `restricted`.

## 4. Подготовка переменных без включения auth

В Railway Variables задайте:

```text
LIBRARY_TOKEN_PEPPER=<новый случайный секрет не короче 32 байт>
LIBRARY_AUTH_ENABLED=false
LIBRARY_PUBLIC_SECTIONS_ENABLED=false
LIBRARY_AUTH_FAIL_CLOSED=true
```

Сначала оставьте `LIBRARY_AUTH_ENABLED=false`. Дождитесь успешного redeploy и
проверьте `/readyz`.

`LIBRARY_TOKEN_PEPPER` нельзя менять после выпуска токенов без их полной
перевыдачи.

## 5. Первый system administrator

В Railway Terminal выполните:

```bash
uv run library-admin tokens bootstrap --name platform-admin
```

Скопируйте поле `token` в password manager. В SQLite сохраняется только HMAC.
Повторный bootstrap запрещён после появления первого токена.

Чтобы не передавать токен аргументом следующих команд, поместите его только в
переменную текущей terminal-сессии:

```bash
read -rsp "Admin token: " LIBRARY_ADMIN_TOKEN
echo
export LIBRARY_ADMIN_TOKEN
```

Переменная не добавляется в Railway Variables и исчезает при закрытии terminal.

## 6. Telegram token

Создайте отдельный токен бота:

```bash
uv run library-admin tokens create \
  --name telegram-bot \
  --subject-type telegram \
  --grant research/main:read,publish
```

Сохраните выведенный `token` в Railway Variable:

```text
LIBRARY_TELEGRAM_ACCESS_TOKEN=<выданный rl_... токен>
```

Не используйте для Telegram административный токен.

## 7. Включение section-авторизации

После сохранения Telegram token измените Railway Variables:

```text
LIBRARY_AUTH_ENABLED=true
LIBRARY_PUBLIC_SECTIONS_ENABLED=false
LIBRARY_AUTH_FAIL_CLOSED=true
```

Для legacy tokens не задавайте широкие grants:

```text
LIBRARY_LEGACY_API_GRANTS=
LIBRARY_LEGACY_MCP_GRANTS=
```

Дождитесь успешного redeploy. Если `/readyz` не проходит, верните
`LIBRARY_AUTH_ENABLED=false`, не меняя pepper и выданные токены, изучите логи и
повторите переключение после исправления.

## 8. Проверка Telegram

В разрешённом Telegram-чате последовательно:

1. отправьте новый тестовый материал;
2. найдите его естественным запросом или `/search`;
3. задайте вопрос по материалу или используйте `/ask`;
4. отправьте материал с изображением и проверьте его сохранение;
5. убедитесь, что в Railway logs нет `permission_denied` и `invalid_token` для
   surface `telegram`.

После проверки выполните в Railway Terminal:

```bash
uv run library-admin migration verify
uv run library-admin tokens list
```

Ожидаются минимум два активных токена: `platform-admin` и `telegram-bot`.

## 9. Отключение compatibility tokens

Так как других клиентов сейчас нет, после успешной проверки Telegram удалите из
Railway Variables:

```text
LIBRARY_API_TOKEN
MCP_AUTH_TOKEN
LIBRARY_LEGACY_API_GRANTS
LIBRARY_LEGACY_MCP_GRANTS
```

Выполните redeploy и повторите Telegram smoke test. На этом переход с общих
секретов завершён.

## 10. Будущие клиенты

Пример AutoResearch:

```bash
uv run library-admin tokens create \
  --name autoresearch-outbox \
  --subject-type service \
  --grant research/main:read,publish
```

Пример агента backend-проекта:

```bash
uv run library-admin sections create memento/backend \
  --title "Backend" --policy restricted

uv run library-admin tokens create \
  --name backend-agent \
  --subject-type agent \
  --grant memento/backend:read,publish \
  --grant research/main:read
```

Каждый независимый клиент получает собственный токен. Отзыв:

```bash
uv run library-admin tokens revoke <token-id>
```

## 11. Критерии завершения

- `library-admin migration verify` возвращает `ok: true`;
- Telegram сохраняет и читает материалы после включения auth;
- `LIBRARY_AUTH_ENABLED=true`;
- `LIBRARY_TOKEN_PEPPER` и `LIBRARY_TELEGRAM_ACCESS_TOKEN` установлены;
- общие `LIBRARY_API_TOKEN` и `MCP_AUTH_TOKEN` удалены;
- public sections выключены;
- Grafana получает auth success/failure, denials и token counts.
