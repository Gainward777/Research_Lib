from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from controllers.api.auth import require_write
from controllers.api.dependencies import get_container
from controllers.utils.bootstrap.dependencies import ApplicationContainer
from views.api.responses import UploadResponse

router = APIRouter(prefix="/v1/uploads", tags=["uploads"], dependencies=[Depends(require_write)])
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


@router.post("", response_model=UploadResponse)
async def upload(
    file: UploadFile = File(...),
    container: ApplicationContainer = Depends(get_container),
) -> UploadResponse:
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Upload is too large")
    result = await container.attachments.save_upload(content, file.filename, file.content_type)
    return UploadResponse.model_validate(result)
