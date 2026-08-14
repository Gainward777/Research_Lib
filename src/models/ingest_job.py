from datetime import datetime

from pydantic import BaseModel

from models.enums import IngestStatus


class IngestJob(BaseModel):
    id: str
    status: IngestStatus
    attempts: int
    next_attempt_at: datetime | None = None
    error: str | None = None
