import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

from controllers.telegram.action_controller import route_natural_messages
from controllers.telegram.command_controller import ask_command, idea_command, search_command
from controllers.telegram.extra_command_controller import (
    cancel_command,
    collect_command,
    health_command,
    item_command,
    paper_command,
    recent_command,
    related_command,
    save_collection_command,
    schema_command,
)
from controllers.telegram.media_group_controller import MediaGroupCollector
from controllers.telegram.message_controller import handle_message as route_message
from controllers.telegram.router import is_allowed
from controllers.utils.bootstrap.dependencies import ApplicationContainer
from controllers.utils.services.access.context import bind_authorization
from views.telegram.error_view import render_error
from views.telegram.message_view import split_message

Handler = Callable[[Message, ApplicationContainer], Awaitable[str]]
logger = logging.getLogger(__name__)


class TelegramBotRunner:
    def __init__(self, container: ApplicationContainer) -> None:
        self.container = container
        self.bot = Bot(container.settings.telegram_bot_token)
        self.dispatcher = Dispatcher()
        self.task: asyncio.Task[None] | None = None
        self.media_groups = MediaGroupCollector()
        self.media_tasks: set[asyncio.Task[None]] = set()
        self.authorization = container.authorization.anonymous_context()
        self._register_handlers()

    async def _answer(self, message: Message, response: str) -> None:
        for chunk in split_message(response):
            await message.answer(chunk)

    async def _guarded(self, message: Message, handler: Handler) -> None:
        if not is_allowed(message, self.container.settings):
            return
        try:
            with bind_authorization(self.authorization):
                response = await handler(message, self.container)
            await self._answer(message, response)
        except Exception as exc:
            logger.exception("Telegram handler failed")
            await message.answer(render_error(str(exc)))

    def _register_handlers(self) -> None:
        command_handlers: dict[str, Handler] = {
            "search": search_command,
            "ask": ask_command,
            "idea": idea_command,
            "paper": paper_command,
            "item": item_command,
            "related": related_command,
            "recent": recent_command,
            "schema": schema_command,
            "health": health_command,
            "collect": collect_command,
            "save": save_collection_command,
            "cancel": cancel_command,
        }
        for command_name, handler in command_handlers.items():
            self._register_command(command_name, handler)

        @self.dispatcher.message(F.media_group_id)
        async def handle_media_group(message: Message) -> None:
            if not is_allowed(message, self.container.settings):
                return
            self.media_groups.add(message)
            group_id = str(message.media_group_id)
            task = asyncio.create_task(self._settle_media_group(group_id, message))
            self.media_tasks.add(task)
            task.add_done_callback(self.media_tasks.discard)

        @self.dispatcher.message(F.photo | F.document)
        async def handle_media(message: Message) -> None:
            async def route_one(current: Message, container: ApplicationContainer) -> str:
                return await route_natural_messages([current], container)

            await self._guarded(message, route_one)

        @self.dispatcher.message(F.text | F.caption)
        async def handle_text_message(message: Message) -> None:
            await self._guarded(message, route_message)

    def _register_command(self, command_name: str, handler: Handler) -> None:
        async def callback(message: Message) -> None:
            await self._guarded(message, handler)

        self.dispatcher.message.register(callback, Command(command_name))

    async def _settle_media_group(self, group_id: str, response_message: Message) -> None:
        await asyncio.sleep(self.container.settings.library_media_group_settle_seconds)
        messages = self.media_groups.pop(group_id)
        if not messages:
            return
        try:
            with bind_authorization(self.authorization):
                response = await route_natural_messages(messages, self.container)
            await self._answer(response_message, response)
        except Exception as exc:
            logger.exception("Telegram media group handler failed")
            await response_message.answer(render_error(str(exc)))

    async def start(self) -> None:
        token = self.container.settings.library_telegram_access_token.get_secret_value()
        self.authorization = await self.container.authorization.authenticate(
            token or None, legacy_surface="api"
        )
        self.container.authorization.require_valid_token(self.authorization)
        if (
            self.container.settings.library_auth_enabled
            and not self.authorization.authenticated
        ):
            raise ValueError("Telegram access token is not authenticated")
        self.container.observability.recorder.record_auth(
            surface="telegram",
            outcome="success" if self.authorization.authenticated else "anonymous",
            legacy=self.authorization.legacy,
        )
        self.task = asyncio.create_task(self.dispatcher.start_polling(self.bot))

    async def stop(self) -> None:
        for task in list(self.media_tasks):
            task.cancel()
        if self.media_tasks:
            await asyncio.gather(*self.media_tasks, return_exceptions=True)
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
        await self.bot.session.close()
