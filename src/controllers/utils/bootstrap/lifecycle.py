from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from mcp.server.mcpserver import MCPServer

from controllers.utils.bootstrap.dependencies import build_container
from controllers.utils.bootstrap.settings import Settings
from controllers.workers.retry_controller import RetryWorker


def create_lifespan(settings: Settings | None, mcp_server: MCPServer):
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with mcp_server.session_manager.run():
            container = await build_container(settings)
            app.state.container = container
            retry_worker = RetryWorker(container)
            await retry_worker.start()
            app.state.retry_worker = retry_worker
            telegram_runner = None
            if container.settings.telegram_bot_token:
                from controllers.telegram.bot import TelegramBotRunner

                telegram_runner = TelegramBotRunner(container)
                await telegram_runner.start()
            app.state.telegram_runner = telegram_runner
            try:
                yield
            finally:
                await retry_worker.stop()
                if telegram_runner is not None:
                    await telegram_runner.stop()
                await container.close()

    return lifespan
