from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key, require_user
from app.events import broadcaster
from app.models import Recommendation, User

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
def list_recommendations(
    db: Session = Depends(get_db), current_user: User = Depends(require_user)
) -> list[Recommendation]:
    return db.execute(
        select(Recommendation)
        .where(Recommendation.user_id == current_user.id)
        .order_by(Recommendation.created_at.desc())
    ).scalars().all()


@router.patch("/{recommendation_id}", response_model=RecommendationOut)
def update_recommendation(
    recommendation_id: int,
    payload: RecommendationPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
) -> Recommendation:
    rec = db.execute(
        select(Recommendation).where(
            Recommendation.id == recommendation_id, Recommendation.user_id == current_user.id
        )
    ).scalars().first()
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    rec.dismissed = payload.dismissed
    db.commit()
    db.refresh(rec)
    broadcaster.publish(
        "recommendation_updated", {"id": rec.id, "dismissed": rec.dismissed}, user_id=current_user.id
    )
    return rec
