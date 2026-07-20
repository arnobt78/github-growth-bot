from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key
from app.events import broadcaster
from app.models import Recommendation

router = APIRouter(prefix="/recommendations", tags=["recommendations"], dependencies=[Depends(require_api_key)])


class RecommendationOut(BaseModel):
    id: int
    repo_id: int
    category: str
    title: str
    body: str
    validated: bool
    dismissed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RecommendationPatch(BaseModel):
    dismissed: bool


@router.get("", response_model=list[RecommendationOut])
def list_recommendations(db: Session = Depends(get_db)) -> list[Recommendation]:
    return db.execute(select(Recommendation).order_by(Recommendation.created_at.desc())).scalars().all()


@router.patch("/{recommendation_id}", response_model=RecommendationOut)
def update_recommendation(recommendation_id: int, payload: RecommendationPatch, db: Session = Depends(get_db)) -> Recommendation:
    rec = db.get(Recommendation, recommendation_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    rec.dismissed = payload.dismissed
    db.commit()
    db.refresh(rec)
    broadcaster.publish("recommendation_updated", {"id": rec.id, "dismissed": rec.dismissed})
    return rec
