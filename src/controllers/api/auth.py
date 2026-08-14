import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer(auto_error=False)


def _valid(candidate: str, configured: list[str]) -> bool:
    return any(value and secrets.compare_digest(candidate, value) for value in configured)


async def require_read(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> None:
    settings = request.app.state.container.settings
    configured = [settings.library_api_token]
    if not any(configured):
        return
    if credentials is None or not _valid(credentials.credentials, configured):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


async def require_write(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> None:
    await require_read(request, credentials)
