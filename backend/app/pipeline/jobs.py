from sqlalchemy.orm import Session

from app.config import get_settings
from app.events import broadcaster
from app.github_client import GitHubAuthError, GitHubClient
from app.llm_router import LLMRouter
from app.models import Repo, User
from app.pipeline.analyzer import Analyzer
from app.pipeline.assembler import Assembler
from app.pipeline.extractor import Extractor
from app.pipeline.optimizer import Optimizer
from app.pipeline.preprocessor import Preprocessor
from app.pipeline.runner import PipelineRunner
from app.pipeline.synthesizer import Synthesizer
from app.pipeline.validator import Validator
from app.token_crypto import decrypt_token


def build_stages(db: Session, gh_client: GitHubClient, llm_router: LLMRouter) -> list:
    return [
        Extractor(gh_client=gh_client),
        Preprocessor(db_session=db),
        Analyzer(),
        Optimizer(),
        Synthesizer(llm_router=llm_router),
        Validator(),
        Assembler(db_session=db),
    ]


def run_pipeline_for_all_repos(db: Session, user_id: int | None = None) -> None:
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

        owner = db.get(User, repo.user_id)
        gh_client = GitHubClient(token=decrypt_token(owner.access_token_encrypted))
        runner = PipelineRunner(stages=build_stages(db, gh_client, llm_router), db_session=db)
        ctx = runner.run_for_repo(repo)

        if any("needs_reauth" in error for error in ctx.errors):
            failed_auth_user_ids.add(repo.user_id)
            continue

        processed_user_ids.add(repo.user_id)

    for uid in processed_user_ids:
        broadcaster.publish("run_completed", {}, user_id=uid)
