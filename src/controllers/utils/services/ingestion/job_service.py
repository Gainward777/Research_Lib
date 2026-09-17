from controllers.utils.BD.jobs import JobStore
from controllers.utils.BD.sections import SectionStore
from controllers.utils.services.access.authorization_service import AuthorizationService
from controllers.utils.services.access.context import current_authorization
from errors import NotFoundError
from models.access import AuthorizationContext


class JobService:
    def __init__(
        self,
        jobs: JobStore,
        sections: SectionStore,
        authorization: AuthorizationService,
    ) -> None:
        self.jobs = jobs
        self.sections = sections
        self.authorization = authorization

    async def get(
        self,
        job_id: str,
        *,
        auth: AuthorizationContext | None = None,
    ) -> dict[str, object]:
        result = await self.jobs.get(job_id)
        if result is None:
            raise NotFoundError(f"Job not found: {job_id}")
        section = await self.sections.get(str(result["section_id"]))
        if section is None:
            raise NotFoundError(f"Job not found: {job_id}")
        await self.authorization.require_read(auth or current_authorization(), section.ref)
        return result

    async def pending_index_stats(self) -> tuple[int, str | None]:
        return await self.jobs.pending_index_stats()
