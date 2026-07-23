import json
from typing import Any

from app.llm_router import LLMRouter
from app.pipeline.base import Stage
from app.pipeline.content_base import ContentPipelineContext, ContentTask

_KIND_PROMPTS = {
    "readme_suggestion": (
        "You are a technical writer improving a GitHub README. Given the current "
        "README, topics, and description below, write an improved full README in "
        "markdown. Respond with the improved README text only, no commentary.\n\n"
        "Current README:\n{readme}\n\nTopics: {topics}\nDescription: {description}"
    ),
    "missing_doc_suggestion": (
        "Write the full contents of {filename} for this GitHub repository, based on "
        "its README below. Respond with the file content only, no commentary.\n\n"
        "README:\n{readme}"
    ),
    "topic_suggestion": (
        "Suggest GitHub repository topics (lowercase, hyphenated, no '#') to improve "
        "discoverability. Respond with strict JSON only: a list of topic strings, 5-10 items.\n\n"
        "Current topics: {topics}\nDescription: {description}\nREADME:\n{readme}"
    ),
    "seo_suggestion": (
        'Write an SEO-friendly one-sentence repository description and 5-10 discovery '
        'keywords. Respond with strict JSON only: {{"description": "...", "keywords": ["...", "..."]}}.\n\n'
        "Current description: {description}\nTopics: {topics}\nREADME:\n{readme}"
    ),
}


class ContentSynthesizer(Stage):
    name = "content_synthesizer"

    def __init__(self, llm_router: LLMRouter):
        self.llm_router = llm_router

    def run(self, ctx: ContentPipelineContext) -> ContentPipelineContext:
        for task in ctx.tasks:
            self._generate_candidates(ctx, task)
        return ctx

    def _build_prompt(self, task: ContentTask) -> str:
        fields = {
            "readme": task.source_material.get("readme") or "",
            "topics": task.source_material.get("topics") or [],
            "description": task.source_material.get("description") or "",
            "filename": task.source_material.get("filename", ""),
        }
        return _KIND_PROMPTS[task.kind].format(**fields)

    def _generate_candidates(self, ctx: ContentPipelineContext, task: ContentTask) -> None:
        messages = [
            {"role": "system", "content": "You follow the requested output format exactly, with no extra commentary."},
            {"role": "user", "content": self._build_prompt(task)},
        ]
        provider_names = self.llm_router.available_provider_names()
        skip_progression = [set(), set(provider_names[:1]), set(provider_names[:2])]

        for skip in skip_progression:
            try:
                raw_response = self.llm_router.chat_completion(messages, skip_providers=skip)
            except Exception as exc:
                ctx.errors.append(f"content_synthesizer: candidate call failed for {task.kind}/{task.target}: {exc}")
                continue

            candidate = self._parse_candidate(task, raw_response)
            if candidate is not None:
                task.candidates.append(candidate)

    def _parse_candidate(self, task: ContentTask, raw_response: str) -> Any | None:
        if not task.structured:
            text = raw_response.strip()
            return text or None

        try:
            parsed = json.loads(raw_response)
        except (json.JSONDecodeError, TypeError):
            return None

        if task.kind == "topic_suggestion":
            if isinstance(parsed, list) and parsed and all(isinstance(t, str) and t for t in parsed):
                return parsed
            return None

        if task.kind == "seo_suggestion":
            if (
                isinstance(parsed, dict)
                and isinstance(parsed.get("description"), str) and parsed["description"]
                and isinstance(parsed.get("keywords"), list) and parsed["keywords"]
                and all(isinstance(k, str) and k for k in parsed["keywords"])
            ):
                return {"description": parsed["description"], "keywords": parsed["keywords"]}
            return None

        return None
