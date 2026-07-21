# backend/tests/test_pipeline_per_user.py
from unittest.mock import MagicMock, patch

from app.db import SessionLocal
from app.models import PipelineRun, Repo, User
from app.token_crypto import encrypt_token


def _seed_user_with_repo(github_id: str) -> tuple[int, int]:
    db = SessionLocal()
    user = User(
        github_id=github_id,
        username=f"user-{github_id}",
        avatar_url=f"https://avatars.githubusercontent.com/u/{github_id}",
        email=None,
        access_token_encrypted=encrypt_token(f"token-for-{github_id}"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    repo = Repo(owner="octocat", name=f"repo-{github_id}", user_id=user.id)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    user_id, repo_id = user.id, repo.id
    db.close()
    return user_id, repo_id


@patch("app.pipeline.jobs.build_stages")
def test_run_pipeline_scoped_to_one_user(mock_build_stages):
    user_a_id, _repo_a_id = _seed_user_with_repo("111")
    user_b_id, _repo_b_id = _seed_user_with_repo("222")

    mock_runner = MagicMock()
    mock_runner.run_for_repo.side_effect = lambda repo: type("Ctx", (), {"errors": []})()
    with patch("app.pipeline.jobs.PipelineRunner", return_value=mock_runner):
        from app.pipeline.jobs import run_pipeline_for_all_repos

        db = SessionLocal()
        run_pipeline_for_all_repos(db, user_id=user_a_id)
        db.close()

    assert mock_runner.run_for_repo.call_count == 1
    assert mock_runner.run_for_repo.call_args[0][0].user_id == user_a_id
