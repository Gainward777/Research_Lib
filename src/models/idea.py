from pydantic import BaseModel, Field


class Idea(BaseModel):
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
