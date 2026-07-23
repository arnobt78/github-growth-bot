from sqlalchemy.orm import Session

from app.models import Draft
from app.pipeline.base import Stage
from app.pipeline.content_base import ContentPipelineContext, ContentTask


class ContentAssembler(Stage):
    name = "content_assembler"

    def __init__(self, db_session: Session):
        self.db = db_session

    def run(self, ctx: ContentPipelineContext) -> ContentPipelineContext:
        for task in ctx.tasks:
            if not task.valid:
                continue
            self.db.add(Draft(
                user_id=ctx.repo.user_id,
                repo_id=ctx.repo.id,
                kind=task.kind,
                target=task.target,
                content=self._content_for(task),
                status="pending",
            ))
        self.db.commit()
        return ctx

    def _content_for(self, task: ContentTask) -> dict:
        if task.kind == "seo_suggestion":
            return {
                "current": task.current,
                "suggested_description": task.winner["description"],
                "keywords": task.winner["keywords"],
                "reason": task.winner_reason,
            }
        if task.kind == "missing_doc_suggestion":
            return {"suggested": task.winner, "reason": task.winner_reason}
        return {"current": task.current, "suggested": task.winner, "reason": task.winner_reason}
