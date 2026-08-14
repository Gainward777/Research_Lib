import re
from enum import StrEnum


class Intent(StrEnum):
    SAVE = "save"
    SEARCH = "search"
    ASK = "ask"


QUESTION_START = re.compile(
    r"^(кто|что|где|когда|зачем|почему|как|какой|какая|какие|сколько|"
    r"есть ли|можно ли|известно ли|who|what|where|when|why|how|which|is|are|do|does|can)\b",
    re.IGNORECASE,
)
SAVE_START = re.compile(
    r"^(сохрани|сохранить|запиши|записать|добавь|добавить|зафиксируй|"
    r"отч[её]т|результаты|наблюдение|протокол|лог|эксперимент|"
    r"save|store|record|report)\b",
    re.IGNORECASE,
)


def classify_intent(
    text: str,
    *,
    has_attachments: bool = False,
    is_forwarded: bool = False,
) -> Intent:
    """Route conservatively: ambiguous material is stored instead of discarded."""
    stripped = text.strip()
    if stripped.startswith("/search"):
        return Intent.SEARCH
    if stripped.startswith("/ask"):
        return Intent.ASK
    if has_attachments or is_forwarded:
        return Intent.SAVE
    if not stripped or SAVE_START.search(stripped):
        return Intent.SAVE

    # A report is normally multiline. Treat it as material even if
    # it quotes a question or contains question marks inside the body.
    if stripped.count("\n") >= 4:
        return Intent.SAVE

    if stripped.endswith("?") or QUESTION_START.search(stripped):
        return Intent.ASK
    return Intent.SAVE
