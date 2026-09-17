from fastapi import HTTPException, Request, status

from controllers.utils.services.access.context import current_authorization
from models.access import AuthorizationContext


def bearer_from_header(value: str) -> str | None:
    scheme, separator, candidate = value.partition(" ")
    if not separator or scheme.casefold() != "bearer" or not candidate:
        return None
    return candidate


async def require_read(request: Request) -> AuthorizationContext:
    context = current_authorization()
    settings = request.app.state.container.settings
    if context.invalid_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if (
        not settings.library_auth_enabled
        and settings.library_api_token
        and not context.authenticated
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return context


async def require_write(request: Request) -> AuthorizationContext:
    return await require_read(request)
