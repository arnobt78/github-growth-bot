import json

from app.llm_router import LLMRouter
from app.pipeline.base import PipelineContext, Stage


class Synthesizer(Stage):
    name = "synthesizer"

    def __init__(self, llm_router: LLMRouter):
        self.llm_router = llm_router

    def run(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.ranked_findings:
            ctx.recommendations = []
            return ctx

        prompt = self._build_prompt(ctx)
        try:
            raw_response = self.llm_router.chat_completion([
                {"role": "system", "content": "You are a precise GitHub repo growth analyst. Respond with strict JSON only: a list of objects with keys title, body, category. Every number in body must come from the provided data — never invent numbers."},
                {"role": "user", "content": prompt},
            ])
        except Exception as exc:
            ctx.recommendations = []
            ctx.errors.append(f"synthesizer: LLM call failed: {exc}")
            return ctx

        try:
            parsed = json.loads(raw_response)
            if not isinstance(parsed, list):
                ctx.recommendations = []
                ctx.errors.append("synthesizer: LLM response was not a JSON list")
            else:
                ctx.recommendations = parsed
        except (json.JSONDecodeError, TypeError):
            ctx.recommendations = []
            ctx.errors.append("synthesizer: LLM response was not valid JSON")

        return ctx

    def _build_prompt(self, ctx: PipelineContext) -> str:
        return (
            f"Repo: {ctx.repo.owner}/{ctx.repo.name}\n"
            f"Metrics: {ctx.normalized}\n"
            f"Findings to turn into recommendations: {ctx.ranked_findings}\n"
            "Write one recommendation per finding."
        )
