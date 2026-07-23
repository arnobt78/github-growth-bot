import json
import re

from app.llm_router import LLMRouter
from app.pipeline.base import Stage
from app.pipeline.content_base import ContentPipelineContext, ContentTask


class ContentValidator(Stage):
    name = "content_validator"

    def __init__(self, llm_router: LLMRouter):
        self.llm_router = llm_router

    def run(self, ctx: ContentPipelineContext) -> ContentPipelineContext:
        known_numbers = self._known_numbers(ctx)

        for task in ctx.tasks:
            if not task.candidates:
                continue

            self._pick_winner(ctx, task)
            if task.winner is None:
                continue

            if task.structured:
                # Already shape-validated by ContentSynthesizer's _parse_candidate —
                # a topic/keyword list has no free-text number-hallucination risk.
                task.valid = True
            else:
                task.valid = self._numbers_ok(task.winner, known_numbers)
                if not task.valid:
                    ctx.errors.append(
                        f"content_validator: {task.kind}/{task.target} winner cites unverified numbers"
                    )

        return ctx

    def _pick_winner(self, ctx: ContentPipelineContext, task: ContentTask) -> None:
        if len(task.candidates) == 1:
            task.winner = task.candidates[0]
            task.winner_reason = "only candidate generated"
            return

        prompt = (
            f"You are judging {len(task.candidates)} candidate answers for a '{task.kind}' task. "
            "Pick the single best candidate. Respond with strict JSON only: "
            '{"best_index": <int>, "reason": "<one line>"}.\n\n'
            + "\n\n".join(f"Candidate {i}:\n{c}" for i, c in enumerate(task.candidates))
        )
        try:
            raw_response = self.llm_router.chat_completion([
                {"role": "system", "content": "Respond with strict JSON only."},
                {"role": "user", "content": prompt},
            ])
            verdict = json.loads(raw_response)
            best_index = verdict.get("best_index", -1)
            if not isinstance(best_index, int) or not (0 <= best_index < len(task.candidates)):
                return
            task.winner = task.candidates[best_index]
            task.winner_reason = verdict.get("reason")
        except Exception as exc:
            ctx.errors.append(f"content_validator: judge call failed for {task.kind}/{task.target}: {exc}")

    # Matches "42 stars", "15 open issues", etc. — only numbers making a specific
    # repo-metric claim are cross-checked. A blanket "every digit in the document"
    # check over-rejects real README/doc text, which routinely contains incidental
    # numbers (versions, years, ports) that have nothing to do with fabricated stats.
    _METRIC_CLAIM_PATTERN = re.compile(
        r"(\d+)\s*(?:stars?|forks?|watchers?|open issues?|contributors?|downloads?|clones?|views?)",
        re.IGNORECASE,
    )

    def _numbers_ok(self, candidate: str, known_numbers: set[int]) -> bool:
        cited = {int(n) for n in self._METRIC_CLAIM_PATTERN.findall(candidate)}
        return cited.issubset(known_numbers)

    def _known_numbers(self, ctx: ContentPipelineContext) -> set[int]:
        known = {value for value in ctx.raw.values() if isinstance(value, int)}
        # forks/watchers/open-issues live nested under raw["repo"], not top-level —
        # without these, a candidate correctly citing real fork/watcher/issue counts
        # (e.g. carried over from the existing README) gets rejected as unverified.
        repo_data = ctx.raw.get("repo")
        if isinstance(repo_data, dict):
            for key in ("forks_count", "watchers_count", "open_issues_count", "stargazers_count"):
                value = repo_data.get(key)
                if isinstance(value, int):
                    known.add(value)
        return known
