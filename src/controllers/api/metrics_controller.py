import logging
import secrets

from fastapi import APIRouter, Request

from controllers.utils.infrastructure.observability.logging import log_event
from views.api.metrics_view import render_metrics

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/metrics", include_in_schema=False)
async def metrics(request: Request):
    container = request.app.state.container
    settings = container.settings
    if not settings.metrics_endpoint_enabled:
        return render_metrics(b"", "text/plain", status_code=404)

    authorization = request.headers.get("Authorization", "")
    scheme, _, candidate = authorization.partition(" ")
    configured = settings.metrics_auth_token.get_secret_value()
    authorized = (
        bool(configured)
        and scheme.casefold() == "bearer"
        and secrets.compare_digest(candidate, configured)
    )
    if not authorized:
        log_event(
            logger,
            "metrics.auth.failed",
            reason="missing" if not authorization else "invalid",
        )
        return render_metrics(
            b"unauthorized\n",
            "text/plain; charset=utf-8",
            status_code=401,
            authenticate=True,
        )
    return render_metrics(
        container.observability.render_metrics(),
        container.observability.metrics_content_type,
    )
