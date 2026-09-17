from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from controllers.api.auth import require_read, require_write
from controllers.api.dependencies import get_container
from controllers.utils.bootstrap.dependencies import ApplicationContainer
from errors import AuthenticationRequiredError
from models.access import (
    AccessPermission,
    AuthorizationContext,
    SectionReadPolicy,
    SectionRef,
    SectionStatus,
    SubjectType,
)

router = APIRouter(prefix="/v1/admin", tags=["admin"])


class SectionCreateRequest(BaseModel):
    section: SectionRef
    title: str = Field(min_length=1, max_length=200)
    read_policy: SectionReadPolicy = SectionReadPolicy.RESTRICTED


class SectionUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    read_policy: SectionReadPolicy | None = None
    status: SectionStatus | None = None


class GrantRequest(BaseModel):
    section: SectionRef | None = None
    permission: AccessPermission


class TokenCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    subject_type: SubjectType
    expires_at: datetime | None = None
    grants: list[GrantRequest] = Field(default_factory=list)


@router.get("/sections")
async def list_sections(
    auth: AuthorizationContext = Depends(require_read),
    container: ApplicationContainer = Depends(get_container),
) -> list[dict[str, Any]]:
    return [
        item.model_dump(mode="json")
        for item in await container.section_service.list(auth)
    ]


@router.post("/sections")
async def create_section(
    request: SectionCreateRequest,
    auth: AuthorizationContext = Depends(require_write),
    container: ApplicationContainer = Depends(get_container),
) -> dict[str, Any]:
    result = await container.section_service.create(
        auth,
        request.section,
        title=request.title,
        read_policy=request.read_policy,
    )
    return result.model_dump(mode="json")


@router.patch("/sections/{section_id}")
async def update_section(
    section_id: str,
    request: SectionUpdateRequest,
    auth: AuthorizationContext = Depends(require_write),
    container: ApplicationContainer = Depends(get_container),
) -> dict[str, Any]:
    result = await container.section_service.update(
        auth,
        section_id,
        title=request.title,
        read_policy=request.read_policy,
        status=request.status,
    )
    return result.model_dump(mode="json")


def _tokens(container: ApplicationContainer):
    if container.token_service is None:
        raise AuthenticationRequiredError("LIBRARY_TOKEN_PEPPER is not configured")
    return container.token_service


@router.get("/tokens")
async def list_tokens(
    auth: AuthorizationContext = Depends(require_read),
    container: ApplicationContainer = Depends(get_container),
) -> list[dict[str, Any]]:
    return [
        {
            "id": item.id,
            "name": item.name,
            "public_prefix": item.public_prefix,
            "subject_type": item.subject_type.value,
            "expires_at": item.expires_at.isoformat() if item.expires_at else None,
            "revoked_at": item.revoked_at.isoformat() if item.revoked_at else None,
            "last_used_at": item.last_used_at.isoformat() if item.last_used_at else None,
            "created_at": item.created_at.isoformat(),
        }
        for item in await _tokens(container).list(auth)
    ]


@router.post("/tokens")
async def create_token(
    request: TokenCreateRequest,
    auth: AuthorizationContext = Depends(require_write),
    container: ApplicationContainer = Depends(get_container),
) -> dict[str, Any]:
    issued = await _tokens(container).create(
        auth,
        name=request.name,
        subject_type=request.subject_type,
        expires_at=request.expires_at,
        grants=[(grant.section, grant.permission) for grant in request.grants],
    )
    return issued.model_dump(mode="json")


@router.delete("/tokens/{token_id}")
async def revoke_token(
    token_id: str,
    auth: AuthorizationContext = Depends(require_write),
    container: ApplicationContainer = Depends(get_container),
) -> dict[str, str]:
    await _tokens(container).revoke(auth, token_id)
    return {"revoked": token_id}


@router.post("/tokens/{token_id}/grants")
async def add_grant(
    token_id: str,
    request: GrantRequest,
    auth: AuthorizationContext = Depends(require_write),
    container: ApplicationContainer = Depends(get_container),
) -> dict[str, str]:
    await _tokens(container).add_grant(
        auth, token_id, request.section, request.permission
    )
    return {"status": "created"}


@router.delete("/tokens/{token_id}/grants")
async def remove_grant(
    token_id: str,
    request: GrantRequest,
    auth: AuthorizationContext = Depends(require_write),
    container: ApplicationContainer = Depends(get_container),
) -> dict[str, str]:
    await _tokens(container).remove_grant(
        auth, token_id, request.section, request.permission
    )
    return {"status": "removed"}
