import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


class SerializedMutationQueue:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    async def run(self, operation: Callable[[], Awaitable[T]]) -> T:
        async with self._lock:
            return await operation()
