from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key
from app.models import User
from app.token_crypto import encrypt_token

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_api_key)])


class UserUpsert(BaseModel):
    github_id: str
    username: str
    avatar_url: str
    email: str | None
    access_token: str


class UserOut(BaseModel):
    id: int
    github_id: str
    username: str
    avatar_url: str
    email: str | None
    plan: str
    max_tracked_repos: int

    model_config = {"from_attributes": True}


@router.post("/upsert", response_model=UserOut)
def upsert_user(payload: UserUpsert, db: Session = Depends(get_db)) -> User:
    user = db.execute(select(User).where(User.github_id == payload.github_id)).scalars().first()
    encrypted = encrypt_token(payload.access_token)

    if user is None:
        user = User(
            github_id=payload.github_id,
            username=payload.username,
            avatar_url=payload.avatar_url,
            email=payload.email,
            access_token_encrypted=encrypted,
        )
        db.add(user)
    else:
        user.username = payload.username
        user.avatar_url = payload.avatar_url
        user.email = payload.email
        user.access_token_encrypted = encrypted

    db.commit()
    db.refresh(user)
    return user
