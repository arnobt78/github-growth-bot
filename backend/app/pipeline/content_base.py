from dataclasses import dataclass, field
from typing import Any

from app.models import Repo


@dataclass
class ContentTask:
    kind: str            # "readme_suggestion" | "missing_doc_suggestion" | "topic_suggestion" | "seo_suggestion"
    target: str           # "readme" | "<filename>" | "topics" | "description"
    structured: bool      # False = free-text candidate; True = JSON candidate (topic/seo)
    current: Any          # existing value being improved (readme text, topics list, description str, or None)
    source_material: dict[str, Any] = field(default_factory=dict)
    candidates: list[Any] = field(default_factory=list)
    winner: Any = None
    winner_reason: str | None = None
    valid: bool = False


@dataclass
class ContentPipelineContext:
    repo: Repo
    raw: dict[str, Any] = field(default_factory=dict)
    tasks: list[ContentTask] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
