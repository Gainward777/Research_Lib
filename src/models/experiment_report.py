from typing import Any

from pydantic import BaseModel, Field


class ExperimentReport(BaseModel):
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
    code_revision: str | None = None
