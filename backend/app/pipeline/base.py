from dataclasses import dataclass, field
from typing import Any

from app.models import Repo


@dataclass
class PipelineContext:
    repo: Repo
    raw: dict[str, Any] = field(default_factory=dict)
    normalized: dict[str, Any] = field(default_factory=dict)
    findings: list[dict[str, Any]] = field(default_factory=list)
    ranked_findings: list[dict[str, Any]] = field(default_factory=list)
    narrative: str | None = None
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class Stage:
    name: str = "stage"

    def run(self, ctx: PipelineContext) -> PipelineContext:
        raise NotImplementedError
