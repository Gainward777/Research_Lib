from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from controllers.api.auth import require_read
from controllers.api.dependencies import get_container
from controllers.utils.bootstrap.dependencies import ApplicationContainer
from controllers.utils.services.access.context import current_authorization
from errors import NotFoundError

router = APIRouter(prefix="/v1/attachments", tags=["attachments"])


@router.get("/{attachment_id}", dependencies=[Depends(require_read)])
async def download_attachment(
    attachment_id: str,
    container: ApplicationContainer = Depends(get_container),
) -> FileResponse:
    download = await container.attachments.resolve_download(attachment_id)
    section = await container.sections_store.get(download.section_id)
    if section is None:
        raise NotFoundError("Attachment not found")
    await container.authorization.require_read(current_authorization(), section.ref)
    return FileResponse(
        path=download.path,
        media_type=download.mime_type,
        filename=download.filename,
    )
