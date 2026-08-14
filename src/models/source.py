from pydantic import BaseModel

from models.enums import SourceKind


class Source(BaseModel):
    kind: SourceKind
    external_id: str | None = None
