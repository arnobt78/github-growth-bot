import base64
import json
import time

import pytest

from app.internal_auth import _sign, mint_internal_user_token, verify_internal_user_token


def test_mint_and_verify_round_trip():
    token = mint_internal_user_token("12345")
    assert verify_internal_user_token(token) == "12345"


def test_verify_rejects_tampered_signature():
    token = mint_internal_user_token("12345")
    payload_b64, _sig = token.rsplit(".", 1)
    tampered = f"{payload_b64}.deadbeef"
    with pytest.raises(ValueError):
        verify_internal_user_token(tampered)


def test_verify_rejects_expired_token(monkeypatch):
    token = mint_internal_user_token("12345")
    # simulate 61 seconds passing (token TTL is 60s)
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + 61)
    with pytest.raises(ValueError):
        verify_internal_user_token(token)


def test_verify_rejects_payload_missing_sub():
    payload = json.dumps({"exp": 9999999999})  # valid signature, but no "sub" key
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()
    token = f"{payload_b64}.{_sign(payload_b64)}"

    with pytest.raises(ValueError):
        verify_internal_user_token(token)
