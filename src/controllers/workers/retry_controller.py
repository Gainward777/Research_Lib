import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta

from controllers.utils.bootstrap.dependencies import ApplicationContainer
from models.enums import IngestStatus


class RetryWorker:
    def __init__(self, container: ApplicationContainer) -> None:
        self.container = container
        self.task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self.task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self.task is None:
            return
        self.task.cancel()
        with suppress(asyncio.CancelledError):
            await self.task

    async def _run(self) -> None:
        while True:
            await self.process_once()
            await asyncio.sleep(self.container.settings.library_job_poll_seconds)

    async def process_once(self) -> int:
        rows = await self.container.database.fetchall(
            "SELECT * FROM ingest_jobs WHERE status IN (?, ?) ORDER BY created_at LIMIT 20",
            (IngestStatus.PENDING_INDEX.value, IngestStatus.RETRYABLE_FAILED.value),
        )
        processed = 0
        for row in rows:
            next_attempt = row["next_attempt_at"]
            if next_attempt and datetime.fromisoformat(next_attempt) > datetime.now(UTC):
                continue
            attempts = int(row["attempts"]) + 1
            try:
                item, _slug = await self.container.items.get(row["item_id"])
                await self.container.gbrain.index(item)
                await self.container.repository.mark_indexed(item.id)
                await self.container.database.execute(
                    "UPDATE ingest_jobs SET status=?, attempts=?, error=NULL, "
                    "next_attempt_at=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (IngestStatus.COMPLETED.value, attempts, row["id"]),
                )
            except Exception as exc:
                terminal = attempts >= self.container.settings.library_ingest_max_retries
                status = (
                    IngestStatus.PERMANENTLY_FAILED if terminal else IngestStatus.RETRYABLE_FAILED
                )
                next_at = None
                if not terminal:
                    delay = min(300, 2**attempts)
                    next_at = (datetime.now(UTC) + timedelta(seconds=delay)).isoformat()
                await self.container.database.execute(
                    "UPDATE ingest_jobs SET status=?, attempts=?, error=?, next_attempt_at=?, "
                    "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (status.value, attempts, str(exc), next_at, row["id"]),
                )
            processed += 1
        return processed
