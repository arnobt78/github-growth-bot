from dataclasses import dataclass
from datetime import date, timezone, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import LLMUsage


class LLMRouterError(Exception):
    pass


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_key: str
    models: list[str]
    headers_extra: dict[str, str] | None = None


class LLMRouter:
    def __init__(self, settings: Settings, db_session: Session, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self.db = db_session
        self._http = httpx.Client(transport=transport, timeout=30.0)

    def _providers(self) -> list[ProviderConfig]:
        s = self.settings
        candidates = [
            ProviderConfig("groq", "https://api.groq.com/openai/v1", s.groq_api_key,
                            ["openai/gpt-oss-120b", "qwen/qwen3.6-27b", "openai/gpt-oss-20b"]),
            ProviderConfig("gemini", "https://generativelanguage.googleapis.com/v1beta/openai", s.gemini_api_key,
                            ["gemini-2.5-flash"]),
            ProviderConfig("openrouter", "https://openrouter.ai/api/v1", s.openrouter_api_key,
                            ["meta-llama/llama-3.3-70b-instruct:free", "deepseek/deepseek-chat-v3-0324:free"]),
            ProviderConfig("huggingface", "https://router.huggingface.co/v1", s.huggingface_api_key,
                            ["Qwen/Qwen3-Coder-30B-A3B-Instruct"]),
            ProviderConfig("cloudflare",
                            f"https://api.cloudflare.com/client/v4/accounts/{s.cloudflare_account_id}/ai/v1",
                            s.cloudflare_api_key, ["@cf/meta/llama-3.3-70b-instruct-fp8-fast"]),
            ProviderConfig("vercel-ai-gateway", "https://ai-gateway.vercel.sh/v1", s.vercel_ai_gateway_key,
                            ["openai/gpt-oss-20b"]),
        ]
        return [p for p in candidates if p.api_key]

    def chat_completion(self, messages: list[dict[str, str]], skip_providers: set[str] | None = None) -> str:
        last_error: Exception | None = None
        skip_providers = skip_providers or set()

        for provider in self._providers():
            if provider.name in skip_providers:
                continue
            if self._is_near_limit(provider.name):
                continue
            for model in provider.models:
                try:
                    result = self._call(provider, model, messages)
                    self._record_usage(provider.name)
                    return result
                except Exception as exc:  # any failure: try the next model in this provider
                    last_error = exc
                    continue

        raise LLMRouterError(f"All LLM providers failed: {last_error}")

    def available_provider_names(self) -> list[str]:
        return [p.name for p in self._providers()]

    def _call(self, provider: ProviderConfig, model: str, messages: list[dict[str, str]]) -> str:
        headers = {"Authorization": f"Bearer {provider.api_key}"}
        if provider.headers_extra:
            headers.update(provider.headers_extra)

        response = self._http.post(
            f"{provider.base_url}/chat/completions",
            headers=headers,
            json={"model": model, "messages": messages, "temperature": 0.4},
        )

        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        if not content:
            raise ValueError(f"{provider.name}/{model} returned empty content")
        return content

    def _is_near_limit(self, provider_name: str, daily_ceiling: int = 500) -> bool:
        today = datetime.now(timezone.utc).date()
        usage = self.db.execute(
            select(LLMUsage).where(LLMUsage.provider == provider_name, LLMUsage.date == today)
        ).scalar_one_or_none()
        return bool(usage and usage.call_count >= daily_ceiling)

    def _record_usage(self, provider_name: str) -> None:
        today = datetime.now(timezone.utc).date()
        usage = self.db.execute(
            select(LLMUsage).where(LLMUsage.provider == provider_name, LLMUsage.date == today)
        ).scalar_one_or_none()
        if usage is None:
            usage = LLMUsage(provider=provider_name, date=today, call_count=0)
            self.db.add(usage)
        usage.call_count += 1
        self.db.commit()
