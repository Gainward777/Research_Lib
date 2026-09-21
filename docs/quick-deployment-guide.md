# Быстрое развёртывание Research Library

Эта инструкция подходит для любого хостинга, который умеет собирать Dockerfile,
выдавать HTTPS-адрес и подключать постоянный диск.

## 1. Подготовьте сервис

1. Подключите репозиторий и собирайте корневой Dockerfile.
2. Подключите постоянный диск в каталог /data. Без него библиотека и токены
   пропадут при пересоздании контейнера.
3. Опубликуйте HTTP-порт приложения. По умолчанию это 8000; хостинг может
   передать свой PORT.
4. Настройте healthcheck на GET /readyz.
5. Включите HTTPS. MCP будет доступен по адресу https://ваш-домен/mcp.

Для самостоятельного Docker-хоста:

    docker build -t research-library:latest .
    docker volume create research-library-data
    docker run -d --name research-library --restart unless-stopped \
      -p 8000:8000 \
      -v research-library-data:/data \
      --env-file .env \
      research-library:latest

## 2. Задайте переменные

Минимальный набор:

    LIBRARY_DATA_ROOT=/data/library
    LIBRARY_PUBLIC_URL=https://library.example.com
    OPENAI_API_KEY=<OpenAI API key>
    LIBRARY_GBRAIN_THINK_MODEL=openai:gpt-4.1-mini
    LIBRARY_ROUTER_MODEL=gpt-4.1-mini

    LIBRARY_AUTH_ENABLED=true
    LIBRARY_AUTH_FAIL_CLOSED=true
    LIBRARY_PUBLIC_SECTIONS_ENABLED=false
    LIBRARY_TOKEN_PEPPER=<случайный секрет не короче 32 байт>

    LOG_LEVEL=INFO

Pepper можно создать командой:

    openssl rand -base64 32

Храните LIBRARY_TOKEN_PEPPER в secret manager. Не меняйте его после выдачи
токенов: при смене pepper все существующие токены перестанут работать.

Старые общие LIBRARY_API_TOKEN и MCP_AUTH_TOKEN для новой установки не нужны.
Telegram пока не включайте: сначала создайте для него отдельный токен.

## 3. Создайте системного администратора

После первого успешного запуска откройте shell именно в работающем контейнере с
подключённым диском /data и выполните:

    library-admin tokens bootstrap --name platform-admin

Для запуска из исходного кода используйте:

    uv run library-admin tokens bootstrap --name platform-admin

Bootstrap работает только один раз, пока токенов ещё нет. Скопируйте поле token
из ответа в password manager: повторно получить этот секрет нельзя.

Для следующих команд передайте токен в переменную только текущей shell-сессии:

    export LIBRARY_ADMIN_TOKEN=<полученный rl_... токен>

Не добавляйте административный токен в постоянные переменные приложения.

## 4. Создайте проекты

Для каждого проекта разработки создайте отдельный закрытый раздел
memento/<project>:

    library-admin sections create memento/backend \
      --title "Backend" --policy restricted

Если проекту нужен собственный раздел исследовательских материалов:

    library-admin sections create research/backend \
      --title "Backend research" --policy restricted

Рекомендуемая схема:

- memento/<project> — решения, checkpoint, история реализации и тесты;
- research/<project> — отчёты, идеи и публикации проекта;
- один проект не должен использовать раздел другого проекта.

## 5. Выдайте разработчикам токены

Создавайте отдельный токен каждому человеку или агенту:

    library-admin tokens create \
      --name ivan-backend \
      --subject-type developer \
      --grant memento/backend:read,publish \
      --grant research/backend:read

Для IDE-агента можно использовать subject-type agent, для CI — ci. Если
разработчик должен управлять разделом и его доступами, выдайте
memento/backend:admin вместо read,publish.

Токен показывается один раз. Передайте его через password manager или secret
manager. Не отправляйте токены в Git, Markdown, Linear или обычный чат.

В агентной среде настройте:

- MCP URL: https://library.example.com/mcp;
- transport: Streamable HTTP;
- заголовок Authorization: Bearer <выданный токен>;
- пакет agent-skills из этого репозитория.

## 6. При необходимости включите Telegram

Создайте отдельный токен, не используя токен администратора:

    library-admin tokens create \
      --name telegram-librarian \
      --subject-type telegram \
      --grant research/main:read,publish

Затем задайте переменные и перезапустите сервис:

    TELEGRAM_BOT_TOKEN=<BotFather token>
    LIBRARY_TELEGRAM_ACCESS_TOKEN=<выданный rl_... токен>
    ALLOWED_TELEGRAM_USER_IDS=[123456789]

## 7. Проверьте установку

1. GET /readyz возвращает 200.
2. POST /mcp без Bearer token возвращает 401.
3. MCP-клиент с токеном разработчика подключается и видит только разрешённые
   разделы.
4. Команды ниже показывают ожидаемые разделы и активные токены:

       library-admin sections list
       library-admin tokens list
       library-admin migration verify

5. Создайте тестовую Memento-запись в одном проекте и убедитесь, что токен другого
   проекта её не находит.

## 8. Эксплуатация

- Регулярно сохраняйте резервную копию всего /data.
- При ротации сначала создайте и проверьте новый токен, затем отзовите старый:

      library-admin tokens revoke <token-id>

- Обновляйте контейнер без удаления постоянного диска.
- Не выдавайте system_admin обычным разработчикам, ботам и CI.
- Если потеряны все system_admin-токены, потребуется восстановление базы из
  резервной копии.
