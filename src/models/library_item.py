from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from models.enums import LibraryItemType, RelationType, SourceKind


def new_library_item_id() -> str:
    return f"lib_{uuid4().hex}"


class Relation(BaseModel):
    type: RelationType
    target_id: str = Field(min_length=1)


class Attachment(BaseModel):
    id: str
    path: str
    sha256: str
    mime_type: str
    size_bytes: int = Field(ge=0)
    original_name: str | None = None


class LibraryItem(BaseModel):
    id: str = Field(default_factory=new_library_item_id)
    type: LibraryItemType
    title: str = Field(min_length=1, max_length=300)
    content: str = ""
    summary: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_kind: SourceKind = SourceKind.API
    source_external_id: str | None = None
    authors: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    related: list[Relation] = Field(default_factory=list)
    attachments: list[Attachment] = Field(default_factory=list)
    schema_version: str = "research-v1"
    metadata: dict[str, Any] = Field(default_factory=dict)
