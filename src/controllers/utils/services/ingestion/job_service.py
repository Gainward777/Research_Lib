from controllers.utils.BD.jobs import JobStore
from errors import NotFoundError


class JobService:
    def __init__(self, jobs: JobStore) -> None:
        self.jobs = jobs

    async def get(self, job_id: str) -> dict[str, object]:
        result = await self.jobs.get(job_id)
        if result is None:
            raise NotFoundError(f"Job not found: {job_id}")
        return result
