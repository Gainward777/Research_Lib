import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from controllers.admin import api_controller as admin_controller
from controllers.api import (
    attachment_controller,
    health_controller,
    idea_controller,
    item_controller,
    job_controller,
    metrics_controller,
    publication_controller,
    report_controller,
    schema_controller,
    search_controller,
    upload_controller,
)
from controllers.api.auth import bearer_from_header
from controllers.mcp.auth import (
    mcp_auth_required_and_missing,
    resolve_mcp_authorization,
)
from controllers.mcp.server import create_mcp_http_app
from controllers.utils.bootstrap.dependencies import GBrainFactory
from controllers.utils.bootstrap.lifecycle import create_lifespan
from controllers.utils.bootstrap.settings import Settings
from controllers.utils.infrastructure.observability.context import (
    bind_request_context,
    safe_request_id,
)
from controllers.utils.infrastructure.observability.logging import log_event
from controllers.utils.services.access.context import bind_authorization
from errors import (
    AuthenticationRequiredError,
    IdempotencyConflictError,
    NotFoundError,
    PermissionDeniedError,
    ResearchLibraryError,
)
from views.api.error_view import render_error

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    gbrain_factory: GBrainFactory | None = None,
) -> FastAPI:
    mcp_server, mcp_http_app = create_mcp_http_app()
    app = FastAPI(
        title="Research Library",
        version="0.1.0",
        description="Persistent Markdown research library for Telegram and external services.",
        lifespan=create_lifespan(settings, mcp_server, gbrain_factory),
    )
    for router in (
        health_controller.router,
        attachment_controller.router,
        admin_controller.router,
        upload_controller.router,
        item_controller.router,
        report_controller.router,
        idea_controller.router,
        publication_controller.router,
        search_controller.router,
        job_controller.router,
        schema_controller.router,
        metrics_controller.router,
    ):
        app.include_router(router)
    app.router.routes.extend(mcp_http_app.routes)

    @app.middleware("http")
    async def request_context_and_auth(request: Request, call_next):
        request_id = safe_request_id(request.headers.get("X-Request-ID"))
        authorization_header = request.headers.get("Authorization", "")
        normalized_path = request.url.path.rstrip("/")
        is_mcp = normalized_path == "/mcp"
        if normalized_path == "/metrics":
            authorization = (
                request.app.state.container.authorization.anonymous_context()
            )
        elif is_mcp:
            authorization = await resolve_mcp_authorization(request)
        else:
            authorization = await request.app.state.container.authorization.authenticate(
                bearer_from_header(authorization_header),
                legacy_surface="api",
            )
        if normalized_path != "/metrics":
            auth_outcome = (
                "failure"
                if authorization.invalid_token
                else "success"
                if authorization.authenticated
                else "anonymous"
            )
            request.app.state.container.observability.recorder.record_auth(
                surface="mcp" if is_mcp else "api",
                outcome=auth_outcome,
                legacy=authorization.legacy,
            )
        with (
            bind_request_context(
                request_id=request_id,
                principal_id=authorization.principal_id,
            ),
            bind_authorization(authorization),
        ):
            rejected = authorization.invalid_token or (
                is_mcp and mcp_auth_required_and_missing(request, authorization)
            )
            if rejected:
                if is_mcp:
                    reason = "missing" if not authorization_header else "invalid"
                    request.app.state.container.observability.recorder.record_mcp_auth_failure(
                        reason=reason
                    )
                    log_event(logger, "mcp.auth.failed", reason=reason)
                response = JSONResponse(
                    status_code=401,
                    content={"error": "invalid_token"},
                    headers={"WWW-Authenticate": "Bearer"},
                )
            else:
                response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_request: Request, exc: NotFoundError):
        return render_error(404, "not_found", str(exc))

    @app.exception_handler(AuthenticationRequiredError)
    async def authentication_handler(_request: Request, exc: AuthenticationRequiredError):
        response = render_error(401, "authentication_required", str(exc))
        response.headers["WWW-Authenticate"] = "Bearer"
        return response

    @app.exception_handler(PermissionDeniedError)
    async def permission_handler(_request: Request, exc: PermissionDeniedError):
        return render_error(403, "permission_denied", str(exc))

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
