import httpx
import pytest

from app.email_client import EmailClient


@pytest.fixture
def success_client():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer fake-resend-key"
        return httpx.Response(200, json={"id": "email-123"})

    transport = httpx.MockTransport(handler)
    http = httpx.Client(base_url="https://api.resend.com", transport=transport)
    return EmailClient(api_key="fake-resend-key", from_address="Bot <bot@example.com>", http_client=http)


@pytest.fixture
def failing_client():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "internal error"})

    transport = httpx.MockTransport(handler)
    http = httpx.Client(base_url="https://api.resend.com", transport=transport)
    return EmailClient(api_key="fake-resend-key", from_address="Bot <bot@example.com>", http_client=http)


def test_send_returns_true_on_success(success_client):
    assert success_client.send("user@example.com", "Subject", "<p>Body</p>") is True


def test_send_returns_false_on_http_error(failing_client):
    assert failing_client.send("user@example.com", "Subject", "<p>Body</p>") is False


def test_send_sends_correct_payload():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = httpx.Request(
            request.method, request.url, headers=request.headers, content=request.content
        ).read()
        import json as json_module
        captured["body"] = json_module.loads(request.content)
        return httpx.Response(200, json={"id": "email-123"})

    transport = httpx.MockTransport(handler)
    http = httpx.Client(base_url="https://api.resend.com", transport=transport)
    client = EmailClient(api_key="k", from_address="Bot <bot@example.com>", http_client=http)

    client.send("user@example.com", "Hello", "<p>Hi</p>")

    assert captured["body"] == {
        "from": "Bot <bot@example.com>",
        "to": ["user@example.com"],
        "subject": "Hello",
        "html": "<p>Hi</p>",
    }
