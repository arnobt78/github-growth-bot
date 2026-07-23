from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.rate_limit import limiter
from app.api.events import router as events_router
from app.api.repos import router as repos_router
from app.api.insights import router as insights_router
from app.api.recommendations import router as recommendations_router
from app.api.drafts import router as drafts_router
from app.api.runs import router as runs_router
from app.api.providers import router as providers_router
from app.api.users import router as users_router
from app.db import SessionLocal
from app.pipeline.jobs import run_pipeline_for_all_repos
from app.pipeline.content_jobs import run_content_pipeline_for_all_repos

settings = get_settings()

scheduler = BackgroundScheduler()


def _scheduled_pipeline_run() -> None:
    db = SessionLocal()
    try:
        run_pipeline_for_all_repos(db)
    finally:
        db.close()


def _scheduled_content_pipeline_run() -> None:
    db = SessionLocal()
    try:
        run_content_pipeline_for_all_repos(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    scheduler.add_job(_scheduled_pipeline_run, "interval", hours=24, id="daily_pipeline_run")
    # Offset 12h from the analytics job's default first-run time so the two
    # daily jobs don't both fire at once and contend for the same LLM
    # provider rate-limit windows.
    scheduler.add_job(
        _scheduled_content_pipeline_run,
        "interval",
        hours=24,
        id="daily_content_pipeline_run",
        next_run_time=datetime.now() + timedelta(hours=12),
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="GitHub Growth Bot API", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(repos_router)
app.include_router(insights_router)
app.include_router(recommendations_router)
app.include_router(drafts_router)
app.include_router(runs_router)
app.include_router(providers_router)
app.include_router(users_router)
app.include_router(events_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
