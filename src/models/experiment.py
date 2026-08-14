from pydantic import BaseModel, Field


class Experiment(BaseModel):
    external_id: str
    title: str
    tags: list[str] = Field(default_factory=list)
