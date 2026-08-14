from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

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
from controllers.mcp.auth import is_mcp_authorized
from controllers.mcp.server import create_mcp_http_app
from controllers.utils.bootstrap.lifecycle import create_lifespan
from controllers.utils.bootstrap.settings import Settings
from errors import IdempotencyConflictError, NotFoundError, ResearchLibraryError
from views.api.error_view import render_error


def create_app(settings: Settings | None = None) -> FastAPI:
    mcp_server, mcp_http_app = create_mcp_http_app()
    app = FastAPI(
        title="Research Library",
        version="0.1.0",
        description="Persistent Markdown research library for Telegram and external services.",
        lifespan=create_lifespan(settings, mcp_server),
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
    app.router.routes.extend(mcp_http_app.routes)

    @app.middleware("http")
    async def authenticate_mcp(request: Request, call_next):
        if request.url.path.rstrip("/") == "/mcp" and not is_mcp_authorized(request):
            return JSONResponse(
                status_code=401,
                content={"error": "invalid_mcp_token"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)

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
