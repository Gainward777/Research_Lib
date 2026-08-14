from pydantic import BaseModel, Field

from models.enums import LibraryItemType


class SaveResult(BaseModel):
    item_id: str
    slug: str
    created: bool
    indexed: bool
    warnings: list[str] = Field(default_factory=list)


class SearchHit(BaseModel):
    item_id: str
    slug: str
    type: LibraryItemType
    title: str
    summary: str = ""
    score: float = 0.0
    tags: list[str] = Field(default_factory=list)


class AnswerResult(BaseModel):
    answer: str
    sources: list[SearchHit] = Field(default_factory=list)
