import json
from uuid import uuid4

from controllers.utils.BD.sqlite import Database
from models.enums import IngestStatus


class JobStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def create_pending_index(
        self, item_id: str, error: str, section_id: str
    ) -> str:
        job_id = f"job_{uuid4().hex}"
        await self.database.execute(
            "INSERT INTO ingest_jobs(id, item_id, section_id, status, error) "
            "VALUES (?, ?, ?, ?, ?)",
            (job_id, item_id, section_id, IngestStatus.PENDING_INDEX.value, error),
        )
        return job_id

    async def get(self, job_id: str) -> dict[str, object] | None:
        row = await self.database.fetchone("SELECT * FROM ingest_jobs WHERE id = ?", (job_id,))
        if row is None:
            return None
        result = dict(row)
        if result.get("result_json"):
            result["result"] = json.loads(str(result.pop("result_json")))
        return result

    async def pending_index_stats(self) -> tuple[int, str | None]:
        row = await self.database.fetchone(
            "SELECT COUNT(*) AS jobs, MIN(created_at) AS oldest "
            "FROM ingest_jobs WHERE status IN (?, ?)",
            (
                IngestStatus.PENDING_INDEX.value,
                IngestStatus.RETRYABLE_FAILED.value,
            ),
        )
        if row is None:
            return 0, None
        oldest = str(row["oldest"]) if row["oldest"] is not None else None
        return int(row["jobs"]), oldest
