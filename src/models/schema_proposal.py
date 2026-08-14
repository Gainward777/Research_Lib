from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SchemaProposal(BaseModel):
    id: str
    kind: str
    name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    created_at: datetime
