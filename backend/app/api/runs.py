from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key
from app.events import broadcaster
from app.models import PipelineRun, StageRun

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


@router.get("", response_model=list[PipelineRunOut])
def list_runs(db: Session = Depends(get_db)) -> list[PipelineRun]:
    return db.execute(select(PipelineRun).order_by(PipelineRun.started_at.desc())).scalars().all()


@router.post("", response_model=list[PipelineRunOut], status_code=202)
def trigger_run(db: Session = Depends(get_db)) -> list[PipelineRun]:
    from app.pipeline.jobs import run_pipeline_for_all_repos
    run_pipeline_for_all_repos(db)
    broadcaster.publish("run_completed", {})
    return db.execute(select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(1)).scalars().all()


@router.get("/{run_id}/stages", response_model=list[StageRunOut])
def list_run_stages(run_id: int, db: Session = Depends(get_db)) -> list[StageRun]:
    run = db.get(PipelineRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return db.execute(
        select(StageRun).where(StageRun.pipeline_run_id == run_id).order_by(StageRun.id)
    ).scalars().all()
