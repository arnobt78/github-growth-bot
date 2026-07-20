from app.pipeline.base import PipelineContext, Stage


class Optimizer(Stage):
    name = "optimizer"
    max_findings = 10

    def run(self, ctx: PipelineContext) -> PipelineContext:
        ranked = sorted(ctx.findings, key=lambda f: f["impact"] - f["effort"], reverse=True)
        ctx.ranked_findings = ranked[: self.max_findings]
        return ctx
