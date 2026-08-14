import json

from controllers.utils.BD.sqlite import Database


class CollectionStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def start(self, chat_id: int) -> None:
        await self.database.execute(
            "INSERT INTO collection_sessions(chat_id, payload_json) VALUES (?, '[]') "
            "ON CONFLICT(chat_id) DO UPDATE SET payload_json='[]', "
            "updated_at=CURRENT_TIMESTAMP",
            (chat_id,),
        )

    async def is_active(self, chat_id: int) -> bool:
        return (
            await self.database.fetchone(
                "SELECT 1 FROM collection_sessions WHERE chat_id = ?", (chat_id,)
            )
            is not None
        )

    async def add(self, chat_id: int, text: str) -> int:
        row = await self.database.fetchone(
            "SELECT payload_json FROM collection_sessions WHERE chat_id = ?", (chat_id,)
        )
        if row is None:
            raise ValueError("Collection session is not active")
        items = json.loads(row["payload_json"])
        items.append(text)
        await self.database.execute(
            "UPDATE collection_sessions SET payload_json=?, updated_at=CURRENT_TIMESTAMP "
            "WHERE chat_id=?",
            (json.dumps(items, ensure_ascii=False), chat_id),
        )
        return len(items)

    async def pop(self, chat_id: int) -> list[str]:
        row = await self.database.fetchone(
            "SELECT payload_json FROM collection_sessions WHERE chat_id = ?", (chat_id,)
        )
        if row is None:
            return []
        await self.cancel(chat_id)
        return list(json.loads(row["payload_json"]))

    async def cancel(self, chat_id: int) -> None:
        await self.database.execute("DELETE FROM collection_sessions WHERE chat_id = ?", (chat_id,))
