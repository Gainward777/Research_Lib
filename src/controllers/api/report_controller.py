from fastapi import APIRouter, Depends, Header

from controllers.api.auth import require_write
from controllers.api.dependencies import get_container
from controllers.api.requests import ExperimentReportRequest
from controllers.utils.bootstrap.dependencies import ApplicationContainer
from models.experiment_report import ExperimentReport
from views.api.responses import SaveResponse

router = APIRouter(
    prefix="/v1/experiment-reports", tags=["reports"], dependencies=[Depends(require_write)]
)


@router.post("", response_model=SaveResponse)
async def save_report(
    request: ExperimentReportRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    container: ApplicationContainer = Depends(get_container),
) -> SaveResponse:
    report = ExperimentReport.model_validate(
        request.model_dump(
            exclude={
                "section",
                "source",
                "artifact_upload_ids",
                "source_library_item_ids",
                "autoresearch_url",
            }
        )
    )
    result = await container.reports.save(
        report,
        attachment_upload_ids=request.artifact_upload_ids,
        idempotency_key=idempotency_key,
        section=request.section,
    )
    return SaveResponse.model_validate(result.model_dump())
