from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key
from app.events import broadcaster
from app.models import Repo

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
def list_repos(db: Session = Depends(get_db)) -> list[Repo]:
    return db.query(Repo).all()


@router.post("", response_model=RepoOut, status_code=201)
def create_repo(payload: RepoCreate, db: Session = Depends(get_db)) -> Repo:
    repo = Repo(owner=payload.owner, name=payload.name)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    broadcaster.publish("repo_added", {"id": repo.id})
    return repo


@router.get("/{repo_id}", response_model=RepoOut)
def get_repo(repo_id: int, db: Session = Depends(get_db)) -> Repo:
    repo = db.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    return repo


@router.delete("/{repo_id}", status_code=204)
def delete_repo(repo_id: int, db: Session = Depends(get_db)) -> None:
    repo = db.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    db.delete(repo)
    db.commit()
    broadcaster.publish("repo_removed", {"id": repo_id})
