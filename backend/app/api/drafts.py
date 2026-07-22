from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key, require_user
from app.events import broadcaster
from app.models import Draft, User

router = APIRouter(prefix="/drafts", tags=["drafts"], dependencies=[Depends(require_api_key)])


class DraftOut(BaseModel):
    id: int
    repo_id: int | None
    kind: str
    target: str
    content: dict
    status: str
    created_at: datetime
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}


class DraftPatch(BaseModel):
    status: Literal["approved", "rejected"]


@router.get("", response_model=list[DraftOut])
def list_drafts(db: Session = Depends(get_db), current_user: User = Depends(require_user)) -> list[Draft]:
    return db.execute(
        select(Draft).where(Draft.user_id == current_user.id).order_by(Draft.created_at.desc())
    ).scalars().all()


@router.patch("/{draft_id}", response_model=DraftOut)
def review_draft(
    draft_id: int,
    payload: DraftPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
) -> Draft:
    draft = db.execute(
        select(Draft).where(Draft.id == draft_id, Draft.user_id == current_user.id)
    ).scalars().first()
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.status != "pending":
        raise HTTPException(status_code=409, detail="Draft has already been reviewed")

    draft.status = payload.status
    # Reuse created_at's own tzinfo (set by models._now(), i.e. UTC) rather than a
    # bare datetime.now() — keeps reviewed_at timezone-aware and consistent with it.
    draft.reviewed_at = datetime.now(draft.created_at.tzinfo)
    db.commit()
    db.refresh(draft)
    broadcaster.publish("draft_updated", {"id": draft.id, "status": draft.status}, user_id=current_user.id)
    return draft
