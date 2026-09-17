import hashlib
import json
from typing import Any

from controllers.utils.BD.sqlite import Database
from errors import IdempotencyConflictError


def payload_hash(payload: Any) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ReceiptStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def get(
        self, key: str, section_id: str, expected_hash: str
    ) -> dict[str, Any] | None:
        row = await self.database.fetchone(
            "SELECT payload_hash, response_json FROM idempotency_receipts "
            "WHERE key = ? AND section_id = ?",
            (key, section_id),
        )
        if row is None:
            return None
        if row["payload_hash"] != expected_hash:
            raise IdempotencyConflictError("Idempotency key was already used with another payload")
        return json.loads(row["response_json"]) if row["response_json"] else None

    async def save(
        self, key: str, section_id: str, digest: str, response: dict[str, Any]
    ) -> None:
        await self.database.execute(
            "INSERT INTO idempotency_receipts("
            "key, section_id, payload_hash, status, response_json"
            ") VALUES (?, ?, ?, 'completed', ?)",
            (key, section_id, digest, json.dumps(response, ensure_ascii=False)),
        )
