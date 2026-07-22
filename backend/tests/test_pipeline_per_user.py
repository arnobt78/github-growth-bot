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


def _add_repo_for_user(user_id: int, name: str) -> int:
    db = SessionLocal()
    repo = Repo(owner="octocat", name=name, user_id=user_id)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    repo_id = repo.id
    db.close()
    return repo_id


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


@patch("app.events.broadcaster.publish")
@patch("app.pipeline.jobs.build_stages")
def test_run_pipeline_auth_failure_circuit_breaker_is_isolated_per_user(mock_build_stages, mock_publish):
    # User A: repo A1 fails with an expired/rejected token, so repo A2 must
    # never be attempted (circuit breaker trips per-user, not globally).
    user_a_id, repo_a1_id = _seed_user_with_repo("333")
    repo_a2_id = _add_repo_for_user(user_a_id, "repo-333-second")

    # User B: healthy token, must be processed normally in the same batch,
    # unaffected by user A's auth failure.
    user_b_id, repo_b1_id = _seed_user_with_repo("777")

    def run_for_repo_side_effect(repo):
        if repo.user_id == user_a_id:
            return type(
                "Ctx", (), {"errors": ["extractor: needs_reauth: GitHub token rejected"]}
            )()
        return type("Ctx", (), {"errors": []})()

    mock_runner = MagicMock()
    mock_runner.run_for_repo.side_effect = run_for_repo_side_effect
    with patch("app.pipeline.jobs.PipelineRunner", return_value=mock_runner):
        from app.pipeline.jobs import run_pipeline_for_all_repos

        db = SessionLocal()
        run_pipeline_for_all_repos(db)  # no user_id filter: the daily-job path
        db.close()

    attempted_repo_ids = [call.args[0].id for call in mock_runner.run_for_repo.call_args_list]

    # A1 attempted, A2 skipped by the circuit breaker after A1's auth failure.
    assert attempted_repo_ids.count(repo_a1_id) == 1
    assert repo_a2_id not in attempted_repo_ids

    # B1 still processed despite user A's failure earlier in the same batch.
    assert attempted_repo_ids.count(repo_b1_id) == 1

    # run_completed only fires for users who had at least one successfully
    # processed repo this run; user A had none (all repos hit needs_reauth).
    published_user_ids = [call.kwargs.get("user_id") for call in mock_publish.call_args_list]
    assert user_b_id in published_user_ids
    assert user_a_id not in published_user_ids
