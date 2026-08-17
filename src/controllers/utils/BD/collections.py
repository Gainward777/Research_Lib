import json
from dataclasses import dataclass

from controllers.utils.BD.sqlite import Database


@dataclass
class CollectedMaterial:
    text_parts: list[str]
    upload_ids: list[str]


def _decode_material(payload_json: str) -> CollectedMaterial:
    raw = json.loads(payload_json)
    if isinstance(raw, dict):
        return CollectedMaterial(
            text_parts=[
                str(value) for value in raw.get("text_parts", []) if isinstance(value, str)
            ],
            upload_ids=[
                str(value) for value in raw.get("upload_ids", []) if isinstance(value, str)
            ],
        )
    if isinstance(raw, list):
        return CollectedMaterial(text_parts=[str(value) for value in raw], upload_ids=[])
    return CollectedMaterial(text_parts=[], upload_ids=[])


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

    async def add(
        self,
        chat_id: int,
        text: str,
        upload_ids: list[str] | None = None,
    ) -> int:
        row = await self.database.fetchone(
            "SELECT payload_json FROM collection_sessions WHERE chat_id = ?", (chat_id,)
        )
        if row is None:
            raise ValueError("Collection session is not active")
        material = _decode_material(row["payload_json"])
        if text:
            material.text_parts.append(text)
        material.upload_ids.extend(upload_ids or [])
        payload = json.dumps(
            {
                "text_parts": material.text_parts,
                "upload_ids": material.upload_ids,
            },
            ensure_ascii=False,
        )
        await self.database.execute(
            "UPDATE collection_sessions SET payload_json=?, updated_at=CURRENT_TIMESTAMP "
            "WHERE chat_id=?",
            (payload, chat_id),
        )
        return len(material.text_parts) + int(bool(material.upload_ids))

    async def pop(self, chat_id: int) -> list[str]:
        return (await self.pop_material(chat_id)).text_parts

    async def pop_material(self, chat_id: int) -> CollectedMaterial:
        row = await self.database.fetchone(
            "SELECT payload_json FROM collection_sessions WHERE chat_id = ?", (chat_id,)
        )
        if row is None:
            return CollectedMaterial(text_parts=[], upload_ids=[])
        material = _decode_material(row["payload_json"])
        await self.cancel(chat_id)
        return material

    async def cancel(self, chat_id: int) -> None:
        await self.database.execute("DELETE FROM collection_sessions WHERE chat_id = ?", (chat_id,))
