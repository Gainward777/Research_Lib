from pydantic import BaseModel, Field


class Publication(BaseModel):
    title: str
    url: str | None = None
    summary: str = ""
    authors: list[str] = Field(default_factory=list)
