from typing import Any

from pydantic import BaseModel, Field, HttpUrl

from models.enums import LibraryItemType, RelationType, SourceKind


class CreateItemRequest(BaseModel):
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


class ExperimentReportRequest(BaseModel):
    source: str = "autoresearch"
    experiment_external_id: str
    iteration_external_id: str
    report_version: int = Field(ge=1)
    title: str
    summary: str
    hypothesis: str = ""
    configuration: dict[str, Any] = Field(default_factory=dict)
    metrics_summary: dict[str, Any] = Field(default_factory=dict)
    conclusions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    artifact_upload_ids: list[str] = Field(default_factory=list)
    source_library_item_ids: list[str] = Field(default_factory=list)
    autoresearch_url: HttpUrl | None = None
    code_revision: str | None = None


class IdeaRequest(BaseModel):
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)


class PublicationRequest(BaseModel):
    title: str
    summary: str = ""
    url: HttpUrl | None = None
    authors: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    types: list[LibraryItemType] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=100)
    synthesize: bool = False


class RelationRequest(BaseModel):
    type: RelationType
    target_id: str


class SchemaProposalRequest(BaseModel):
    kind: str
    name: str
    payload: dict[str, Any] = Field(default_factory=dict)
