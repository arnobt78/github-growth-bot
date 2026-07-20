import httpx
import pytest

from app.config import Settings
from app.db import Base, SessionLocal, engine
from app.llm_router import LLMRouter, LLMRouterError


def _settings(**overrides) -> Settings:
    base = dict(
        database_url="sqlite:///:memory:",
        api_key="k",
        github_token="t",
        groq_api_key="groq-key",
        gemini_api_key="gemini-key",
        openrouter_api_key="",
        huggingface_api_key="",
        cloudflare_api_key="",
        cloudflare_account_id="",
        vercel_ai_gateway_key="",
    )
    base.update(overrides)
    return Settings(**base)


def _db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def test_uses_first_provider_on_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "groq.com" in str(request.url)
        return httpx.Response(200, json={"choices": [{"message": {"content": "hello from groq"}}]})

    router = LLMRouter(settings=_settings(), db_session=_db(), transport=httpx.MockTransport(handler))
    result = router.chat_completion([{"role": "user", "content": "hi"}])
    assert result == "hello from groq"


def test_falls_back_to_next_provider_on_429():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "groq.com" in str(request.url):
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "hello from gemini"}}]})

    router = LLMRouter(settings=_settings(), db_session=_db(), transport=httpx.MockTransport(handler))
    result = router.chat_completion([{"role": "user", "content": "hi"}])
    assert result == "hello from gemini"
    assert any("groq.com" in c for c in calls)
    assert any("generativelanguage" in c for c in calls)


def test_falls_back_to_next_model_in_same_provider_on_non_retryable_failure():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        body = request.content.decode() if request.content else ""
        if "openai/gpt-oss-120b" in body:
            # Simulate a network-level failure that is NOT a 429/5xx status.
            raise httpx.ConnectTimeout("connect timed out", request=request)
        if "qwen/qwen3.6-27b" in body:
            return httpx.Response(200, json={"choices": [{"message": {"content": "hello from second groq model"}}]})
        raise AssertionError(f"unexpected request body: {body}")

    router = LLMRouter(settings=_settings(), db_session=_db(), transport=httpx.MockTransport(handler))
    result = router.chat_completion([{"role": "user", "content": "hi"}])
    assert result == "hello from second groq model"
    assert all("groq.com" in c for c in calls)
    assert len(calls) == 2


def test_raises_when_all_providers_fail():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "down"})

    router = LLMRouter(settings=_settings(), db_session=_db(), transport=httpx.MockTransport(handler))
    with pytest.raises(LLMRouterError):
        router.chat_completion([{"role": "user", "content": "hi"}])
