from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key
from app.models import BenchmarkRepo, Recommendation, Repo, Snapshot

router = APIRouter(prefix="/repos", tags=["insights"], dependencies=[Depends(require_api_key)])


class SnapshotOut(BaseModel):
    id: int
    date: date
    stars: int
    forks: int
    watchers: int
    open_issues: int
    views_14d: int
    unique_views_14d: int
    clones_14d: int
    unique_clones_14d: int

    model_config = {"from_attributes": True}


@router.get("/{repo_id}/snapshots", response_model=list[SnapshotOut])
def list_snapshots(repo_id: int, db: Session = Depends(get_db)) -> list[Snapshot]:
    _require_repo(repo_id, db)
    return db.execute(select(Snapshot).where(Snapshot.repo_id == repo_id).order_by(Snapshot.date)).scalars().all()


@router.get("/{repo_id}/insights")
def get_insights(repo_id: int, db: Session = Depends(get_db)) -> dict:
    _require_repo(repo_id, db)
    latest = db.execute(
        select(Snapshot).where(Snapshot.repo_id == repo_id).order_by(Snapshot.date.desc())
    ).scalars().first()
    recommendations = db.execute(
        select(Recommendation).where(Recommendation.repo_id == repo_id, Recommendation.dismissed.is_(False))
    ).scalars().all()

    return {
        "latest_stars": latest.stars if latest else 0,
        "latest_forks": latest.forks if latest else 0,
        "recommendation_count": len(recommendations),
    }


@router.get("/{repo_id}/benchmarks")
def list_benchmarks(repo_id: int, db: Session = Depends(get_db)) -> list[dict]:
    _require_repo(repo_id, db)
    rows = db.execute(select(BenchmarkRepo).where(BenchmarkRepo.source_repo_id == repo_id)).scalars().all()
    return [{"full_name": r.full_name, "stars": r.stars, "forks": r.forks, "topics": r.topics} for r in rows]


def _require_repo(repo_id: int, db: Session) -> Repo:
    repo = db.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    return repo
