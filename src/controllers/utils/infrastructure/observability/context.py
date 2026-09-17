import hashlib
import re
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, replace
from uuid import uuid4

REQUEST_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_.:-]{1,128}$")


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    principal_id: str = ""
    project: str = ""
    repository: str = ""
    work_item: str = ""


_request_context: ContextVar[RequestContext | None] = ContextVar(
    "research_library_request_context", default=None
)


def new_request_id() -> str:
    return f"req_{uuid4().hex}"


def safe_request_id(candidate: str | None) -> str:
    if candidate and REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return new_request_id()


def principal_id_from_authorization(authorization: str) -> str:
    scheme, _, token = authorization.partition(" ")
    if scheme.casefold() != "bearer" or not token:
        return ""
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    return f"principal_{digest}"


def current_request_context() -> RequestContext:
    context = _request_context.get()
    return context if context is not None else RequestContext(request_id=new_request_id())


def ensure_request_context() -> Token[RequestContext | None] | None:
    if _request_context.get() is not None:
        return None
    return _request_context.set(RequestContext(request_id=new_request_id()))


def reset_request_context(token: Token[RequestContext | None] | None) -> None:
    if token is not None:
        _request_context.reset(token)


@contextmanager
def bind_request_context(
    *,
    request_id: str,
    principal_id: str = "",
    project: str = "",
    repository: str = "",
    work_item: str = "",
):
    token = _request_context.set(
        RequestContext(
            request_id=request_id,
            principal_id=principal_id,
            project=project,
            repository=repository,
            work_item=work_item,
        )
    )
    try:
        yield
    finally:
        _request_context.reset(token)


def set_request_scope(*, project: str = "", repository: str = "", work_item: str = "") -> None:
    current = _request_context.get()
    if current is None:
        current = RequestContext(request_id=new_request_id())
    _request_context.set(
        replace(
            current,
            project=project or current.project,
            repository=repository or current.repository,
            work_item=work_item or current.work_item,
        )
    )
