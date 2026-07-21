from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_db
from app.deps import require_api_key, require_user
from app.models import PipelineRun, StageRun, User

router = APIRouter(prefix="/runs", tags=["runs"], dependencies=[Depends(require_api_key)])


class PipelineRunOut(BaseModel):
    id: int
    status: str
    started_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class StageRunOut(BaseModel):
    id: int
    stage_name: str
    status: str
    duration_ms: int
    error: str | None

    model_config = {"from_attributes": True}


class TriggerRunOut(BaseModel):
    status: str


@router.get("", response_model=list[PipelineRunOut])
def list_runs(db: Session = Depends(get_db), current_user: User = Depends(require_user)) -> list[PipelineRun]:
    return db.execute(
        select(PipelineRun)
        .where(PipelineRun.user_id == current_user.id)
        .order_by(PipelineRun.started_at.desc())
    ).scalars().all()


@router.post("", response_model=TriggerRunOut, status_code=202)
def trigger_run(
    background_tasks: BackgroundTasks, current_user: User = Depends(require_user)
) -> TriggerRunOut:
    background_tasks.add_task(_run_pipeline_background, current_user.id)
    return TriggerRunOut(status="started")


def _run_pipeline_background(user_id: int) -> None:
    from app.pipeline.jobs import run_pipeline_for_all_repos

    db = SessionLocal()
    try:
        run_pipeline_for_all_repos(db, user_id=user_id)
    finally:
        db.close()


@router.get("/{run_id}/stages", response_model=list[StageRunOut])
def list_run_stages(
    run_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)
) -> list[StageRun]:
    run = db.execute(
        select(PipelineRun).where(PipelineRun.id == run_id, PipelineRun.user_id == current_user.id)
    ).scalars().first()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return db.execute(
        select(StageRun).where(StageRun.pipeline_run_id == run_id).order_by(StageRun.id)
    ).scalars().all()
