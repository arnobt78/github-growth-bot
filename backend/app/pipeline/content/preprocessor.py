from app.pipeline.base import Stage
from app.pipeline.content_base import ContentPipelineContext

_MAX_README_CHARS = 6000


class ContentPreprocessor(Stage):
    name = "content_preprocessor"

    def run(self, ctx: ContentPipelineContext) -> ContentPipelineContext:
        for task in ctx.tasks:
            readme = task.source_material.get("readme")
            if readme:
                task.source_material["readme"] = readme.strip()[:_MAX_README_CHARS]
        return ctx
