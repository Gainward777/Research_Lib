from typing import Any

from pydantic import BaseModel, Field

from models.enums import LibraryItemType, SourceKind


class CreateItemCommand(BaseModel):
    type: LibraryItemType
    title: str = Field(min_length=1, max_length=300)
    content: str = ""
    summary: str = ""
    source_kind: SourceKind = SourceKind.API
    source_external_id: str | None = None
    authors: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    attachment_upload_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchCommand(BaseModel):
    query: str = Field(min_length=1)
    types: list[LibraryItemType] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=100)
    synthesize: bool = False
