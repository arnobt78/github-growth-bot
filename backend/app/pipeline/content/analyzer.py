from app.pipeline.base import Stage
from app.pipeline.content_base import ContentPipelineContext, ContentTask

_MIN_TOPICS = 5


class ContentAnalyzer(Stage):
    name = "content_analyzer"

    def run(self, ctx: ContentPipelineContext) -> ContentPipelineContext:
        raw = ctx.raw
        topics = raw.get("topics", [])
        tasks: list[ContentTask] = [
            ContentTask(
                kind="readme_suggestion",
                target="readme",
                structured=False,
                current=raw.get("readme"),
                source_material={"readme": raw.get("readme") or "", "topics": topics, "description": raw.get("description")},
            ),
        ]

        for filename in raw.get("missing_docs", []):
            tasks.append(ContentTask(
                kind="missing_doc_suggestion",
                target=filename,
                structured=False,
                current=None,
                source_material={"filename": filename, "readme": raw.get("readme") or ""},
            ))

        if len(topics) < _MIN_TOPICS:
            tasks.append(ContentTask(
                kind="topic_suggestion",
                target="topics",
                structured=True,
                current=topics,
                source_material={"topics": topics, "readme": raw.get("readme") or "", "description": raw.get("description")},
            ))

        tasks.append(ContentTask(
            kind="seo_suggestion",
            target="description",
            structured=True,
            current=raw.get("description"),
            source_material={"description": raw.get("description"), "readme": raw.get("readme") or "", "topics": topics},
        ))

        ctx.tasks = tasks
        return ctx
