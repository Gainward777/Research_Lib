from typing import Any

from pydantic import BaseModel, Field

from models.enums import LibraryItemType
from models.library_item import LibraryItem
from models.results import AnswerResult, SaveResult, SearchHit


class SaveResponse(SaveResult):
    pass


class ItemResponse(BaseModel):
    item: LibraryItem
    slug: str


class SearchResponse(BaseModel):
    hits: list[SearchHit]


class AnswerResponse(AnswerResult):
    pass


class UploadResponse(BaseModel):
    upload_id: str
    sha256: str
    mime_type: str
    size_bytes: int


class RelationResponse(BaseModel):
    item_id: str
    slug: str
    related_count: int


class HealthResponse(BaseModel):
    status: str
    checks: dict[str, bool] = Field(default_factory=dict)


class JobResponse(BaseModel):
    id: str
    status: str
    item_id: str | None = None
    attempts: int = 0
    next_attempt_at: str | None = None
    error: str | None = None
    result: dict[str, Any] | None = None


class ProposalResponse(BaseModel):
    id: str
    kind: str
    name: str
    payload: dict[str, Any]
    status: str
    created_at: str
    applied_at: str | None = None


class RecentItemResponse(BaseModel):
    id: str
    type: LibraryItemType
    title: str
    slug: str
