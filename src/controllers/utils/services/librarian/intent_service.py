from enum import StrEnum


class Intent(StrEnum):
    SAVE = "save"
    SEARCH = "search"
    ASK = "ask"


def classify_intent(text: str) -> Intent:
    stripped = text.strip()
    if stripped.startswith("/search"):
        return Intent.SEARCH
    if stripped.startswith("/ask") or stripped.endswith("?"):
        return Intent.ASK
    return Intent.SAVE
