from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.internal_auth import verify_internal_user_token


def _rate_limit_key(request: Request) -> str:
    # Key by the verified github_id when a valid internal user token is
    # present, so per-user limits hold even behind a shared IP (office
    # network, corporate NAT). The token itself rotates every request (60s
    # TTL, minted fresh per call) so it can't be used as the key directly —
    # only the github_id it decodes to is stable.
    token = request.headers.get("x-internal-user-token", "")
    if token:
        try:
            return f"user:{verify_internal_user_token(token)}"
        except ValueError:
            pass
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key)
