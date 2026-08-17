TELEGRAM_MESSAGE_LIMIT = 4096


def split_message(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Split at Telegram's limit while preserving every character exactly."""
    if limit <= 0:
        raise ValueError("Telegram message limit must be positive")
    if not text:
        return [""]
    return [text[offset : offset + limit] for offset in range(0, len(text), limit)]
