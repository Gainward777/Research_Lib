from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token

from models.access import AuthorizationContext, AuthPrincipal

_ANONYMOUS = AuthorizationContext(
    principal=AuthPrincipal(id="anonymous", name="Anonymous"),
    anonymous=True,
)
_context: ContextVar[AuthorizationContext] = ContextVar(
    "library_authorization_context", default=_ANONYMOUS
)


def current_authorization() -> AuthorizationContext:
    return _context.get()


def set_authorization(context: AuthorizationContext) -> Token[AuthorizationContext]:
    return _context.set(context)


def reset_authorization(token: Token[AuthorizationContext]) -> None:
    _context.reset(token)


@contextmanager
def bind_authorization(context: AuthorizationContext) -> Iterator[None]:
    token = set_authorization(context)
    try:
        yield
    finally:
        reset_authorization(token)
