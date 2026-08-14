from fastapi import APIRouter, Depends

from controllers.api.auth import require_read
from controllers.api.dependencies import get_container
from controllers.utils.bootstrap.dependencies import ApplicationContainer
from views.api.job_view import render_job
from views.api.responses import JobResponse

router = APIRouter(prefix="/v1/jobs", tags=["jobs"], dependencies=[Depends(require_read)])


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str, container: ApplicationContainer = Depends(get_container)
) -> JobResponse:
    return render_job(await container.jobs.get(job_id))
