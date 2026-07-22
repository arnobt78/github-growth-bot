import base64
import hashlib
import hmac
import json
import time

from app.config import get_settings

TOKEN_TTL_SECONDS = 60


def _sign(payload_b64: str) -> str:
    settings = get_settings()
    return hmac.new(
        settings.internal_auth_secret.encode(), payload_b64.encode(), hashlib.sha256
    ).hexdigest()


def mint_internal_user_token(github_id: str) -> str:
    """Backend-side minting exists only so tests can construct valid tokens
    without duplicating the HMAC scheme inline. Production tokens are minted
    by the frontend (frontend/lib/internal-auth.ts), server-side, from a
    verified Auth.js session — never by the browser."""
    payload = json.dumps({"sub": github_id, "exp": int(time.time()) + TOKEN_TTL_SECONDS})
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()
    return f"{payload_b64}.{_sign(payload_b64)}"


def verify_internal_user_token(token: str) -> str:
    try:
        payload_b64, signature_hex = token.rsplit(".", 1)
    except ValueError:
        raise ValueError("Malformed internal token")

    if not hmac.compare_digest(_sign(payload_b64), signature_hex):
        raise ValueError("Invalid internal token signature")

    padding = "=" * (-len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
    try:
        exp = payload["exp"]
        sub = payload["sub"]
    except KeyError:
        raise ValueError("Malformed internal token payload")
    if exp < time.time():
        raise ValueError("Expired internal token")
    return str(sub)
