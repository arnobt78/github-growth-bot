from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.internal_auth import verify_internal_user_token
from app.models import User


def require_api_key(authorization: str = Header(default="")) -> None:
    settings = get_settings()
    expected = f"Bearer {settings.api_key}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def require_user(
    x_internal_user_token: str = Header(default=""),
    db: Session = Depends(get_db),
) -> User:
    if not x_internal_user_token:
        raise HTTPException(status_code=401, detail="Invalid or missing user token")

    try:
        github_id = verify_internal_user_token(x_internal_user_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or missing user token")

    user = db.execute(select(User).where(User.github_id == github_id)).scalars().first()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or missing user token")
    return user
