import asyncio
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import aiosqlite


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection: aiosqlite.Connection | None = None
        self._write_lock = asyncio.Lock()

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = await aiosqlite.connect(self.path)
        self.connection.row_factory = aiosqlite.Row
        await self.connection.execute("PRAGMA journal_mode=WAL")
        await self.connection.execute("PRAGMA foreign_keys=ON")
        await self.connection.execute("PRAGMA busy_timeout=5000")
        await self.connection.commit()

    async def close(self) -> None:
        if self.connection is not None:
            await self.connection.close()
            self.connection = None

    def _connection(self) -> aiosqlite.Connection:
        if self.connection is None:
            raise RuntimeError("Database is not connected")
        return self.connection

    async def execute(self, sql: str, parameters: Iterable[Any] = ()) -> None:
        async with self._write_lock:
            connection = self._connection()
            await connection.execute(sql, tuple(parameters))
            await connection.commit()

    async def execute_returning_id(self, sql: str, parameters: Iterable[Any] = ()) -> int:
        async with self._write_lock:
            connection = self._connection()
            cursor = await connection.execute(sql, tuple(parameters))
            await connection.commit()
            return int(cursor.lastrowid or 0)

    async def executescript(self, sql: str) -> None:
        async with self._write_lock:
            connection = self._connection()
            await connection.executescript(sql)
            await connection.commit()

    async def fetchone(self, sql: str, parameters: Iterable[Any] = ()) -> aiosqlite.Row | None:
        cursor = await self._connection().execute(sql, tuple(parameters))
        return await cursor.fetchone()

    async def fetchall(self, sql: str, parameters: Iterable[Any] = ()) -> list[aiosqlite.Row]:
        cursor = await self._connection().execute(sql, tuple(parameters))
        return list(await cursor.fetchall())
