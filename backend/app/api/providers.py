from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key
from app.models import LLMUsage

router = APIRouter(prefix="/providers", tags=["providers"], dependencies=[Depends(require_api_key)])


@router.get("/status")
def provider_status(db: Session = Depends(get_db)) -> list[dict]:
    today = datetime.now(timezone.utc).date()
    rows = db.execute(select(LLMUsage).where(LLMUsage.date == today)).scalars().all()
    return [{"provider": r.provider, "calls_today": r.call_count} for r in rows]
