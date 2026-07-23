from sqlalchemy.orm import Session

from app.config import get_settings
from app.events import broadcaster
from app.github_client import GitHubClient
from app.llm_router import LLMRouter
from app.models import Repo, User
from app.pipeline.content.analyzer import ContentAnalyzer
from app.pipeline.content.assembler import ContentAssembler
from app.pipeline.content.extractor import ContentExtractor
from app.pipeline.content.optimizer import ContentOptimizer
from app.pipeline.content.preprocessor import ContentPreprocessor
from app.pipeline.content.synthesizer import ContentSynthesizer
from app.pipeline.content.validator import ContentValidator
from app.pipeline.content_base import ContentPipelineContext
from app.pipeline.runner import PipelineRunner
from app.token_crypto import decrypt_token


def build_content_stages(db: Session, gh_client: GitHubClient, llm_router: LLMRouter) -> list:
    return [
        ContentExtractor(gh_client=gh_client),
        ContentAnalyzer(),
        ContentPreprocessor(),
        ContentOptimizer(),
        ContentSynthesizer(llm_router=llm_router),
        ContentValidator(llm_router=llm_router),
        ContentAssembler(db_session=db),
    ]


def run_content_pipeline_for_all_repos(db: Session, user_id: int | None = None) -> None:
    settings = get_settings()
    llm_router = LLMRouter(settings=settings, db_session=db)

    query = db.query(Repo)
    if user_id is not None:
        query = query.filter(Repo.user_id == user_id)
    repos = query.all()

    failed_auth_user_ids: set[int] = set()
    processed_user_ids: set[int] = set()

    for repo in repos:
        if repo.user_id in failed_auth_user_ids:
            continue

        try:
            owner = db.get(User, repo.user_id)
            gh_client = GitHubClient(token=decrypt_token(owner.access_token_encrypted))
        except Exception:
            # Same rationale as app.pipeline.jobs.run_pipeline_for_all_repos: owner
            # lookup / token decryption happens outside PipelineRunner's own
            # per-stage exception isolation, so it must be caught here explicitly.
            failed_auth_user_ids.add(repo.user_id)
            continue

        runner = PipelineRunner(
            stages=build_content_stages(db, gh_client, llm_router),
            db_session=db,
            context_factory=ContentPipelineContext,
            pipeline_kind="content",
        )
        ctx = runner.run_for_repo(repo)

        if any("needs_reauth" in error for error in ctx.errors):
            failed_auth_user_ids.add(repo.user_id)
            continue

        processed_user_ids.add(repo.user_id)

    for uid in processed_user_ids:
        broadcaster.publish("drafts_generated", {}, user_id=uid)
