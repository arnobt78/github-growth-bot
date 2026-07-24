from unittest.mock import MagicMock, patch

from app.db import SessionLocal
from app.models import Draft, PipelineRun, Repo, User
from app.pipeline.content_jobs import run_content_pipeline_for_all_repos


def _fake_gh_client():
    gh = MagicMock()
    gh.get_repo.return_value = {"topics": ["cli"], "description": "A tool", "stargazers_count": 10}
    gh.get_readme.return_value = "# Hello"
    gh.has_file.return_value = True  # no missing docs, keeps this test focused
    gh.list_releases.return_value = []
    return gh


def _fake_chat_completion(messages, skip_providers=None):
    # ContentSynthesizer calls chat_completion 3x per task (skip-progression) to
    # generate candidates, then ContentValidator calls it again to judge between
    # candidates when a task has more than one. A single fixed return_value can't
    # serve both roles (the judge call needs valid JSON), so this distinguishes
    # them by the prompt content, mirroring how the real LLM responses would differ
    # by request. Non-readme (structured) tasks deliberately get non-JSON back so
    # they produce no candidates, keeping the assertions focused on the readme task
    # per the plan's own test comment ("at least the readme_suggestion task").
    user_content = messages[-1]["content"]
    if user_content.startswith("You are judging"):
        return '{"best_index": 0, "reason": "most accurate"}'
    if user_content.startswith("You are a technical writer"):
        return "# Improved README"
    return "not json"


def _fake_llm_router():
    llm = MagicMock()
    llm.available_provider_names.return_value = ["groq"]
    llm.chat_completion.side_effect = _fake_chat_completion
    return llm


@patch("app.pipeline.content_jobs.broadcaster.publish")
@patch("app.pipeline.content_jobs.GitHubClient")
@patch("app.pipeline.content_jobs.LLMRouter")
def test_runs_content_pipeline_and_publishes_per_user(mock_llm_cls, mock_gh_cls, mock_publish, seed_user):
    mock_gh_cls.return_value = _fake_gh_client()
    mock_llm_cls.return_value = _fake_llm_router()

    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world", user_id=seed_user)
    db.add(repo)
    db.commit()
    db.refresh(repo)

    run_content_pipeline_for_all_repos(db, user_id=seed_user)

    run_row = db.query(PipelineRun).filter_by(pipeline_kind="content").first()
    assert run_row is not None

    drafts = db.query(Draft).filter_by(repo_id=repo.id).all()
    assert len(drafts) >= 1  # at least the readme_suggestion task

    mock_publish.assert_called_once_with("drafts_generated", {}, user_id=seed_user)
    db.close()


@patch("app.pipeline.content_jobs.broadcaster.publish")
def test_skips_repos_for_user_with_undecryptable_token(mock_publish, seed_user):
    db = SessionLocal()
    user = db.get(User, seed_user)
    user.access_token_encrypted = "not-valid-fernet-ciphertext"
    db.commit()

    repo = Repo(owner="octocat", name="hello-world", user_id=seed_user)
    db.add(repo)
    db.commit()

    run_content_pipeline_for_all_repos(db, user_id=seed_user)

    assert db.query(Draft).count() == 0
    mock_publish.assert_not_called()
    db.close()


@patch("app.pipeline.content_jobs.notify_drafts_ready")
@patch("app.pipeline.content_jobs.broadcaster.publish")
@patch("app.pipeline.content_jobs.GitHubClient")
@patch("app.pipeline.content_jobs.LLMRouter")
def test_notify_false_by_default_sends_nothing(mock_llm_cls, mock_gh_cls, mock_publish, mock_notify, seed_user):
    mock_gh_cls.return_value = _fake_gh_client()
    mock_llm_cls.return_value = _fake_llm_router()

    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world", user_id=seed_user)
    db.add(repo)
    db.commit()

    run_content_pipeline_for_all_repos(db, user_id=seed_user)  # notify defaults False
    db.close()

    mock_notify.assert_not_called()


@patch("app.pipeline.content_jobs.notify_drafts_ready")
@patch("app.pipeline.content_jobs.broadcaster.publish")
@patch("app.pipeline.content_jobs.GitHubClient")
@patch("app.pipeline.content_jobs.LLMRouter")
def test_notify_true_sends_drafts_ready_with_count(mock_llm_cls, mock_gh_cls, mock_publish, mock_notify, seed_user):
    mock_gh_cls.return_value = _fake_gh_client()
    mock_llm_cls.return_value = _fake_llm_router()

    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world", user_id=seed_user)
    db.add(repo)
    db.commit()

    run_content_pipeline_for_all_repos(db, user_id=seed_user, notify=True)

    mock_notify.assert_called_once()
    call_user, call_count = mock_notify.call_args[0]
    assert call_user.id == seed_user
    assert call_count >= 1  # at least the readme_suggestion draft
    db.close()


@patch("app.pipeline.content_jobs.notify_drafts_ready")
@patch("app.pipeline.content_jobs.broadcaster.publish")
def test_notify_true_skips_when_zero_drafts_created(mock_publish, mock_notify, seed_user):
    db = SessionLocal()
    user = db.get(User, seed_user)
    user.access_token_encrypted = "not-valid-fernet-ciphertext"
    db.commit()

    repo = Repo(owner="octocat", name="hello-world", user_id=seed_user)
    db.add(repo)
    db.commit()

    run_content_pipeline_for_all_repos(db, user_id=seed_user, notify=True)
    db.close()

    mock_notify.assert_not_called()
