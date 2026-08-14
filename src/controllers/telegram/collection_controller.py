from collections import defaultdict


class CollectionController:
    def __init__(self) -> None:
        self.sessions: dict[int, list[str]] = defaultdict(list)

    def start(self, chat_id: int) -> None:
        self.sessions[chat_id] = []

    def add(self, chat_id: int, text: str) -> None:
        self.sessions[chat_id].append(text)

    def save(self, chat_id: int) -> str:
        return "\n\n".join(self.sessions.pop(chat_id, []))

    def cancel(self, chat_id: int) -> None:
        self.sessions.pop(chat_id, None)
