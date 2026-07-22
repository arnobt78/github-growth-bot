from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key
from app.models import LLMUsage

router = APIRouter(prefix="/providers", tags=["providers"], dependencies=[Depends(require_api_key)])


class ProviderStatusOut(BaseModel):
    provider: str
    calls_today: int


@router.get("/status", response_model=list[ProviderStatusOut])
def provider_status(db: Session = Depends(get_db)) -> list[dict]:
    today = datetime.now(timezone.utc).date()
    rows = db.execute(select(LLMUsage).where(LLMUsage.date == today)).scalars().all()
    return [{"provider": r.provider, "calls_today": r.call_count} for r in rows]
