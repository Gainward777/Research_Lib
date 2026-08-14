import secrets

from fastapi import Request


def is_mcp_authorized(request: Request) -> bool:
    configured = request.app.state.container.settings.mcp_auth_token
    if not configured:
        return True
    scheme, _, candidate = request.headers.get("Authorization", "").partition(" ")
    return scheme.casefold() == "bearer" and secrets.compare_digest(candidate, configured)
