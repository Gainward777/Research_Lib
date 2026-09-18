from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class DevelopmentContextKind(StrEnum):
    DECISION = "decision"
    CHECKPOINT = "checkpoint"
    IMPLEMENTATION_SNAPSHOT = "implementation_snapshot"
    PROBLEM = "problem"
    TEST_EVIDENCE = "test_evidence"


class ContextCreator(StrEnum):
    AGENT = "agent"
    DEVELOPER = "developer"
    CI = "ci"


class ContextVerification(StrEnum):
    UNVERIFIED = "unverified"
    CI_VERIFIED = "ci-verified"
    HUMAN_APPROVED = "human-approved"


class PublishDevelopmentContext(BaseModel):
    context_kind: DevelopmentContextKind
    project: str = Field(default="", max_length=120)
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1)
    summary: str = ""
    repository: str = Field(default="", max_length=240)
    work_item: str | None = Field(default=None, max_length=120)
    work_context_id: str | None = Field(default=None, max_length=120)
    branch: str | None = Field(default=None, max_length=300)
    commit: str | None = Field(default=None, max_length=120)
    paths: list[str] = Field(default_factory=list)
    created_by: ContextCreator = ContextCreator.AGENT
    verification: ContextVerification = ContextVerification.UNVERIFIED
    tags: list[str] = Field(default_factory=list)
    supersedes_item_id: str | None = None
    consulted_context_item_ids: list[str] = Field(default_factory=list, max_length=100)

    @field_validator(
        "project",
        "title",
        "content",
        "repository",
        "work_item",
        "work_context_id",
        "branch",
        "commit",
        "supersedes_item_id",
        mode="before",
    )
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_work_scope(self) -> "PublishDevelopmentContext":
        if not self.work_item and not self.work_context_id:
            raise ValueError("work_item or work_context_id is required")
        return self


class DevelopmentContextQuery(BaseModel):
    query: str = Field(min_length=1)
    project: str = Field(default="", max_length=120)
    repository: str = Field(default="", max_length=240)
    work_item: str | None = Field(default=None, max_length=120)
    limit: int = Field(default=20, ge=1, le=100)

    @field_validator("query", "project", "repository", "work_item", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class DevelopmentContextEntry(BaseModel):
    item_id: str
    slug: str
    context_kind: DevelopmentContextKind
    title: str
    content: str
    summary: str = ""
    project: str
    repository: str = ""
    work_item: str | None = None
    work_context_id: str | None = None
    branch: str | None = None
    commit: str | None = None
    paths: list[str] = Field(default_factory=list)
    created_by: ContextCreator = ContextCreator.AGENT
    verification: ContextVerification = ContextVerification.UNVERIFIED
    supersedes_item_id: str | None = None
    consulted_context_item_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    score: float = 0.0


class DevelopmentContextBundle(BaseModel):
    query: str
    project: str = ""
    repository: str = ""
    work_item: str | None = None
    related_implementations: list[DevelopmentContextEntry] = Field(default_factory=list)
    decisions: list[DevelopmentContextEntry] = Field(default_factory=list)
    known_problems: list[DevelopmentContextEntry] = Field(default_factory=list)
    tests_and_evidence: list[DevelopmentContextEntry] = Field(default_factory=list)
    checkpoints: list[DevelopmentContextEntry] = Field(default_factory=list)
