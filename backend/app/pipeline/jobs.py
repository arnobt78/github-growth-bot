from sqlalchemy.orm import Session

from app.config import get_settings
from app.events import broadcaster
from app.github_client import GitHubClient
from app.llm_router import LLMRouter
from app.models import Repo, User
from app.notifications import notify_needs_reauth, notify_pipeline_degraded
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


def run_pipeline_for_all_repos(db: Session, user_id: int | None = None, notify: bool = False) -> None:
    settings = get_settings()
    llm_router = LLMRouter(settings=settings, db_session=db)

    query = db.query(Repo)
    if user_id is not None:
        query = query.filter(Repo.user_id == user_id)
    repos = query.all()

    failed_auth_user_ids: set[int] = set()
    processed_user_ids: set[int] = set()
    degraded: dict[int, list[str]] = {}

    for repo in repos:
        if repo.user_id in failed_auth_user_ids:
            continue

        try:
            owner = db.get(User, repo.user_id)
            gh_client = GitHubClient(token=decrypt_token(owner.access_token_encrypted))
        except Exception:
            # Owner lookup / token decryption happens outside PipelineRunner's own
            # exception isolation (that only covers stage execution inside
            # run_for_repo), so a missing User row or an undecryptable token
            # (corrupted ciphertext, rotated encryption key) must be caught here
            # explicitly — otherwise it would propagate and abort every other
            # tenant's repos still queued in this same batch.
            failed_auth_user_ids.add(repo.user_id)
            continue

        runner = PipelineRunner(stages=build_stages(db, gh_client, llm_router), db_session=db)
        ctx = runner.run_for_repo(repo)

        if any("needs_reauth" in error for error in ctx.errors):
            failed_auth_user_ids.add(repo.user_id)
            continue

        if ctx.errors:
            degraded.setdefault(repo.user_id, []).append(f"{repo.owner}/{repo.name}")

        processed_user_ids.add(repo.user_id)

    for uid in processed_user_ids:
        broadcaster.publish("run_completed", {}, user_id=uid)

    if notify:
        for uid, repo_names in degraded.items():
            if uid in failed_auth_user_ids:
                # The reauth email is the more actionable, blocking issue for this
                # user in this run — nothing else can be verified as genuinely
                # working until they reconnect, so it wins over the degraded alert.
                continue
            owner = db.get(User, uid)
            if owner is not None:
                notify_pipeline_degraded(owner, repo_names)
        for uid in failed_auth_user_ids:
            owner = db.get(User, uid)
            if owner is not None:
                notify_needs_reauth(db, owner)
