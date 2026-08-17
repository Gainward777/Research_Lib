import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class DialogTurn:
    role: str
    text: str


class DialogContextStore:
    """Bounded in-memory context; durable knowledge still lives only in Markdown."""

    def __init__(self, max_turns: int = 12) -> None:
        self.max_turns = max_turns
        self._turns: dict[int, deque[DialogTurn]] = defaultdict(
            lambda: deque(maxlen=self.max_turns)
        )
        self._lock = asyncio.Lock()

    async def recent(self, chat_id: int) -> list[DialogTurn]:
        async with self._lock:
            return list(self._turns[chat_id])

    async def add_exchange(self, chat_id: int, user_text: str, assistant_text: str) -> None:
        async with self._lock:
            self._turns[chat_id].append(DialogTurn(role="user", text=user_text))
            self._turns[chat_id].append(DialogTurn(role="assistant", text=assistant_text))
