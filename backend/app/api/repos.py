from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key, require_user
from app.events import broadcaster
from app.models import Repo, User
from app.rate_limit import limiter

router = APIRouter(prefix="/repos", tags=["repos"], dependencies=[Depends(require_api_key)])


class RepoCreate(BaseModel):
    owner: str
    name: str


class RepoOut(BaseModel):
    id: int
    owner: str
    name: str
    tracked_since: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[RepoOut])
def list_repos(db: Session = Depends(get_db), current_user: User = Depends(require_user)) -> list[Repo]:
    return db.execute(select(Repo).where(Repo.user_id == current_user.id)).scalars().all()


@router.post("", response_model=RepoOut, status_code=201)
@limiter.limit("10/minute")
def create_repo(
    request: Request,
    payload: RepoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
) -> Repo:
    tracked_count = db.execute(
        select(func.count()).select_from(Repo).where(Repo.user_id == current_user.id)
    ).scalar_one()
    if tracked_count >= current_user.max_tracked_repos:
        raise HTTPException(
            status_code=403,
            detail=f"Repo limit reached ({current_user.max_tracked_repos} on the {current_user.plan} plan).",
        )

    repo = Repo(owner=payload.owner, name=payload.name, user_id=current_user.id)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    broadcaster.publish("repo_added", {"id": repo.id}, user_id=current_user.id)
    return repo


@router.get("/{repo_id}", response_model=RepoOut)
def get_repo(
    repo_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)
) -> Repo:
    repo = db.execute(
        select(Repo).where(Repo.id == repo_id, Repo.user_id == current_user.id)
    ).scalars().first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    return repo


@router.delete("/{repo_id}", status_code=204)
def delete_repo(
    repo_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)
) -> None:
    repo = db.execute(
        select(Repo).where(Repo.id == repo_id, Repo.user_id == current_user.id)
    ).scalars().first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    db.delete(repo)
    db.commit()
    broadcaster.publish("repo_removed", {"id": repo_id}, user_id=current_user.id)
