from fastapi import Request

from controllers.api.auth import bearer_from_header
from models.access import AuthorizationContext


async def resolve_mcp_authorization(request: Request) -> AuthorizationContext:
    container = request.app.state.container
    token = bearer_from_header(request.headers.get("Authorization", ""))
    return await container.authorization.authenticate(token, legacy_surface="mcp")


def mcp_auth_required_and_missing(
    request: Request, context: AuthorizationContext
) -> bool:
    settings = request.app.state.container.settings
    return (
        (settings.library_auth_enabled or bool(settings.mcp_auth_token))
        and not context.authenticated
    )
