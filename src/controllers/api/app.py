from fastapi import FastAPI, Request

from controllers.api import (
    health_controller,
    idea_controller,
    item_controller,
    job_controller,
    publication_controller,
    report_controller,
    schema_controller,
    search_controller,
    upload_controller,
)
from controllers.utils.bootstrap.lifecycle import create_lifespan
from controllers.utils.bootstrap.settings import Settings
from errors import IdempotencyConflictError, NotFoundError, ResearchLibraryError
from views.api.error_view import render_error


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(
        title="Research Library",
        version="0.1.0",
        description="Persistent Markdown research library for Telegram, Codex and AutoResearch.",
        lifespan=create_lifespan(settings),
    )
    for router in (
        health_controller.router,
        upload_controller.router,
        item_controller.router,
        report_controller.router,
        idea_controller.router,
        publication_controller.router,
        search_controller.router,
        job_controller.router,
        schema_controller.router,
    ):
        app.include_router(router)

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_request: Request, exc: NotFoundError):
        return render_error(404, "not_found", str(exc))

    @app.exception_handler(IdempotencyConflictError)
    async def idempotency_handler(_request: Request, exc: IdempotencyConflictError):
        return render_error(409, "idempotency_conflict", str(exc))

    @app.exception_handler(ValueError)
    async def value_error_handler(_request: Request, exc: ValueError):
        return render_error(422, "validation_error", str(exc))

    @app.exception_handler(ResearchLibraryError)
    async def application_error_handler(_request: Request, exc: ResearchLibraryError):
        return render_error(500, "application_error", str(exc))

    return app
