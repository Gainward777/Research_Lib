import json
import logging
from datetime import UTC, datetime
from typing import Any

from controllers.utils.infrastructure.observability.context import (
    current_request_context,
)

FORBIDDEN_FIELDS = {
    "authorization",
    "content",
    "mcp_token",
    "openai_api_key",
    "payload",
    "query",
    "telegram_bot_token",
    "token",
}


class JsonFormatter(logging.Formatter):
    def __init__(self, *, service: str = "", environment: str = "") -> None:
        super().__init__()
        self.service = service
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event_name", record.getMessage()),
            "service": self.service,
            "environment": self.environment,
        }
        event_data = getattr(record, "event_data", {})
        if isinstance(event_data, dict):
            payload.update(
                {
                    key: value
                    for key, value in event_data.items()
                    if key.casefold() not in FORBIDDEN_FIELDS
                }
            )
        if record.exc_info and record.levelno >= logging.ERROR:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_json_logging(
    level: str,
    *,
    service: str = "",
    environment: str = "",
) -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    handler = next(
        (
            candidate
            for candidate in root.handlers
            if getattr(candidate, "_research_library_json_handler", False)
        ),
        None,
    )
    if handler is None:
        handler = logging.StreamHandler()
        handler._research_library_json_handler = True  # type: ignore[attr-defined]
        root.addHandler(handler)
    handler.setFormatter(JsonFormatter(service=service, environment=environment))


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    **fields: object,
) -> None:
    context = current_request_context()
    safe_fields = {
        key: value for key, value in fields.items() if key.casefold() not in FORBIDDEN_FIELDS
    }
    logger.log(
        level,
        event,
        extra={
            "event_name": event,
            "event_data": {
                "request_id": context.request_id,
                "principal_id": context.principal_id,
                "project": context.project,
                "repository": context.repository,
                "work_item": context.work_item,
                **safe_fields,
            },
        },
    )
