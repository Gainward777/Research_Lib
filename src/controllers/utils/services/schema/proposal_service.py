import json
from uuid import uuid4

from controllers.utils.BD.sqlite import Database
from errors import NotFoundError


class ProposalService:
    def __init__(self, database: Database, mutation_mode: str) -> None:
        self.database = database
        self.mutation_mode = mutation_mode

    async def create(self, kind: str, name: str, payload: dict[str, object]) -> dict[str, object]:
        proposal_id = f"proposal_{uuid4().hex}"
        await self.database.execute(
            "INSERT INTO schema_proposals(id, kind, name, payload_json) VALUES (?, ?, ?, ?)",
            (proposal_id, kind, name, json.dumps(payload, ensure_ascii=False)),
        )
        return await self.get(proposal_id)

    async def list(self) -> list[dict[str, object]]:
        rows = await self.database.fetchall(
            "SELECT * FROM schema_proposals ORDER BY created_at DESC"
        )
        return [self._row(row) for row in rows]

    async def get(self, proposal_id: str) -> dict[str, object]:
        row = await self.database.fetchone(
            "SELECT * FROM schema_proposals WHERE id = ?", (proposal_id,)
        )
        if row is None:
            raise NotFoundError(f"Schema proposal not found: {proposal_id}")
        return self._row(row)

    async def apply(self, proposal_id: str) -> dict[str, object]:
        if self.mutation_mode == "disabled":
            raise ValueError("Schema mutations are disabled")
        await self.get(proposal_id)
        await self.database.execute(
            "UPDATE schema_proposals SET status='applied', applied_at=CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (proposal_id,),
        )
        return await self.get(proposal_id)

    @staticmethod
    def _row(row) -> dict[str, object]:
        result = dict(row)
        result["payload"] = json.loads(str(result.pop("payload_json")))
        return result
