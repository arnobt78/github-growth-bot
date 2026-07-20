import re

from app.pipeline.base import PipelineContext, Stage


class Validator(Stage):
    name = "validator"

    def run(self, ctx: PipelineContext) -> PipelineContext:
        known_numbers = self._known_numbers(ctx)

        for rec in ctx.recommendations:
            body_numbers = {int(n) for n in re.findall(r"\d+", rec.get("body", ""))}
            unverified = body_numbers - known_numbers
            rec["validated"] = len(unverified) == 0
            if not rec["validated"]:
                ctx.errors.append(
                    f"validator: recommendation '{rec.get('title')}' cites unverified numbers {unverified}"
                )

        return ctx

    def _known_numbers(self, ctx: PipelineContext) -> set[int]:
        numbers: set[int] = set()
        for value in ctx.normalized.values():
            if isinstance(value, int):
                numbers.add(value)
        for finding in ctx.ranked_findings:
            numbers.update(int(n) for n in re.findall(r"\d+", finding.get("message", "")))
        return numbers
