from app.pipeline.base import Stage
from app.pipeline.content_base import ContentPipelineContext

_MAX_SOURCE_CHARS = 4000


class ContentOptimizer(Stage):
    name = "content_optimizer"

    def run(self, ctx: ContentPipelineContext) -> ContentPipelineContext:
        for task in ctx.tasks:
            readme = task.source_material.get("readme")
            if readme and len(readme) > _MAX_SOURCE_CHARS:
                task.source_material["readme"] = readme[:_MAX_SOURCE_CHARS]
        return ctx
