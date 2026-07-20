from sqlalchemy.orm import Session

from app.config import get_settings
from app.github_client import GitHubClient
from app.llm_router import LLMRouter
from app.models import Repo
from app.pipeline.analyzer import Analyzer
from app.pipeline.assembler import Assembler
from app.pipeline.extractor import Extractor
from app.pipeline.optimizer import Optimizer
from app.pipeline.preprocessor import Preprocessor
from app.pipeline.runner import PipelineRunner
from app.pipeline.synthesizer import Synthesizer
from app.pipeline.validator import Validator


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


def run_pipeline_for_all_repos(db: Session) -> None:
    settings = get_settings()
    gh_client = GitHubClient(token=settings.github_token)
    llm_router = LLMRouter(settings=settings, db_session=db)
    repos = db.query(Repo).all()
    for repo in repos:
        runner = PipelineRunner(stages=build_stages(db, gh_client, llm_router), db_session=db)
        runner.run_for_repo(repo)
