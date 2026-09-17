from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from controllers.api.auth import require_write
from controllers.api.dependencies import get_container
from controllers.utils.bootstrap.dependencies import ApplicationContainer
from models.access import AuthorizationContext, SectionDomain, SectionRef
from views.api.responses import UploadResponse

router = APIRouter(prefix="/v1/uploads", tags=["uploads"])
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


@router.post("", response_model=UploadResponse)
async def upload(
    file: UploadFile = File(...),
    section: str | None = Query(default=None),
    auth: AuthorizationContext = Depends(require_write),
    container: ApplicationContainer = Depends(get_container),
) -> UploadResponse:
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Upload is too large")
    requested = SectionRef.parse(section) if section else None
    section_ref = await container.authorization.resolve_publish_section(
        auth,
        requested,
        domain=requested.domain if requested else SectionDomain.RESEARCH,
    )
    stored_section = await container.sections_store.require(section_ref)
    result = await container.attachments.save_upload(
        content,
        file.filename,
        file.content_type,
        section_id=stored_section.id,
    )
    return UploadResponse.model_validate(result)
