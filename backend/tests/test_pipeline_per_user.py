# backend/tests/test_pipeline_per_user.py
from unittest.mock import MagicMock, patch

from app.db import SessionLocal
from app.models import Repo, User
from app.token_crypto import encrypt_token


def _seed_user_with_corrupted_token(github_id: str) -> tuple[int, int]:
    db = SessionLocal()
    user = User(
        github_id=github_id,
        username=f"user-{github_id}",
        avatar_url=f"https://avatars.githubusercontent.com/u/{github_id}",
        email=None,
        # Not a valid Fernet token at all (corrupted ciphertext / wrong key
        # after rotation) — decrypt_token() will raise cryptography.fernet.InvalidToken.
        access_token_encrypted="garbage-not-a-valid-fernet-token",
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


@patch("app.events.broadcaster.publish")
@patch("app.pipeline.jobs.build_stages")
def test_run_pipeline_survives_undecryptable_token_for_one_user(mock_build_stages, mock_publish):
    # User A has a corrupted/undecryptable access_token_encrypted (e.g. wrong
    # encryption key after rotation). The owner lookup + decrypt_token() call
    # happens OUTSIDE PipelineRunner's own exception isolation, so this must be
    # caught in run_pipeline_for_all_repos itself — otherwise the raised
    # cryptography.fernet.InvalidToken would propagate and abort the whole
    # batch, meaning user B's repo would never even be attempted.
    user_a_id, repo_a_id = _seed_user_with_corrupted_token("444")

    # User B has a valid, decryptable token and must still be processed
    # normally in the same batch (real decrypt_token() runs for both users;
    # only PipelineRunner/build_stages are mocked out).
    user_b_id, repo_b_id = _seed_user_with_repo("555")

    mock_runner = MagicMock()
    mock_runner.run_for_repo.side_effect = lambda repo: type("Ctx", (), {"errors": []})()
    with patch("app.pipeline.jobs.PipelineRunner", return_value=mock_runner):
        from app.pipeline.jobs import run_pipeline_for_all_repos

        db = SessionLocal()
        run_pipeline_for_all_repos(db)  # no user_id filter: the daily-job path
        db.close()

    attempted_repo_ids = [call.args[0].id for call in mock_runner.run_for_repo.call_args_list]

    # User A's repo was never handed to the runner — it failed before that,
    # at the decrypt step — but the batch did not abort.
    assert repo_a_id not in attempted_repo_ids

    # User B's repo was still processed despite user A's decrypt failure
    # earlier in the same batch.
    assert attempted_repo_ids.count(repo_b_id) == 1

    published_user_ids = [call.kwargs.get("user_id") for call in mock_publish.call_args_list]
    assert user_b_id in published_user_ids
    assert user_a_id not in published_user_ids


@patch("app.pipeline.jobs.notify_needs_reauth")
@patch("app.pipeline.jobs.notify_pipeline_degraded")
@patch("app.events.broadcaster.publish")
@patch("app.pipeline.jobs.build_stages")
def test_notify_false_by_default_sends_nothing(mock_build_stages, mock_publish, mock_notify_degraded, mock_notify_reauth):
    user_id, _repo_id = _seed_user_with_repo("901")

    mock_runner = MagicMock()
    mock_runner.run_for_repo.side_effect = lambda repo: type(
        "Ctx", (), {"errors": ["extractor: boom"]}
    )()
    with patch("app.pipeline.jobs.PipelineRunner", return_value=mock_runner):
        from app.pipeline.jobs import run_pipeline_for_all_repos

        db = SessionLocal()
        run_pipeline_for_all_repos(db, user_id=user_id)  # notify defaults False
        db.close()

    mock_notify_degraded.assert_not_called()
    mock_notify_reauth.assert_not_called()


@patch("app.pipeline.jobs.notify_needs_reauth")
@patch("app.pipeline.jobs.notify_pipeline_degraded")
@patch("app.events.broadcaster.publish")
@patch("app.pipeline.jobs.build_stages")
def test_notify_true_sends_degraded_alert_with_repo_names(mock_build_stages, mock_publish, mock_notify_degraded, mock_notify_reauth):
    user_id, repo_id = _seed_user_with_repo("902")

    mock_runner = MagicMock()
    mock_runner.run_for_repo.side_effect = lambda repo: type(
        "Ctx", (), {"errors": ["extractor: boom"]}
    )()
    with patch("app.pipeline.jobs.PipelineRunner", return_value=mock_runner):
        from app.pipeline.jobs import run_pipeline_for_all_repos

        db = SessionLocal()
        run_pipeline_for_all_repos(db, user_id=user_id, notify=True)
        db.close()

    mock_notify_degraded.assert_called_once()
    call_user, call_repo_names = mock_notify_degraded.call_args[0]
    assert call_user.id == user_id
    assert call_repo_names == ["octocat/repo-902"]
    mock_notify_reauth.assert_not_called()


@patch("app.pipeline.jobs.notify_needs_reauth")
@patch("app.pipeline.jobs.notify_pipeline_degraded")
@patch("app.events.broadcaster.publish")
@patch("app.pipeline.jobs.build_stages")
def test_notify_true_sends_reauth_alert(mock_build_stages, mock_publish, mock_notify_degraded, mock_notify_reauth):
    user_id, _repo_id = _seed_user_with_repo("903")

    mock_runner = MagicMock()
    mock_runner.run_for_repo.side_effect = lambda repo: type(
        "Ctx", (), {"errors": ["extractor: needs_reauth: GitHub token rejected"]}
    )()
    with patch("app.pipeline.jobs.PipelineRunner", return_value=mock_runner):
        from app.pipeline.jobs import run_pipeline_for_all_repos

        db = SessionLocal()
        run_pipeline_for_all_repos(db, user_id=user_id, notify=True)
        db.close()

    mock_notify_reauth.assert_called_once()
    reauth_db_arg, reauth_user_arg = mock_notify_reauth.call_args[0]
    assert reauth_user_arg.id == user_id
    mock_notify_degraded.assert_not_called()


@patch("app.pipeline.jobs.notify_needs_reauth")
@patch("app.pipeline.jobs.notify_pipeline_degraded")
@patch("app.events.broadcaster.publish")
@patch("app.pipeline.jobs.build_stages")
def test_notify_true_skips_degraded_alert_when_same_user_also_needs_reauth(
    mock_build_stages, mock_publish, mock_notify_degraded, mock_notify_reauth
):
    # Same user tracks two repos: repo A (processed first) hits real,
    # non-auth errors and lands the user in `degraded`; repo B (processed
    # after) hits needs_reauth and lands the same user in
    # `failed_auth_user_ids`. Only the reauth email should be sent — the
    # degraded alert must be suppressed to avoid a confusing double
    # notification in the same run.
    user_id, repo_a_id = _seed_user_with_repo("904")
    repo_b_id = _add_repo_for_user(user_id, "repo-904-second")

    def run_for_repo_side_effect(repo):
        if repo.id == repo_a_id:
            return type("Ctx", (), {"errors": ["extractor: boom"]})()
        return type(
            "Ctx", (), {"errors": ["extractor: needs_reauth: GitHub token rejected"]}
        )()

    mock_runner = MagicMock()
    mock_runner.run_for_repo.side_effect = run_for_repo_side_effect
    with patch("app.pipeline.jobs.PipelineRunner", return_value=mock_runner):
        from app.pipeline.jobs import run_pipeline_for_all_repos

        db = SessionLocal()
        run_pipeline_for_all_repos(db, user_id=user_id, notify=True)
        db.close()

    mock_notify_reauth.assert_called_once()
    reauth_db_arg, reauth_user_arg = mock_notify_reauth.call_args[0]
    assert reauth_user_arg.id == user_id
    mock_notify_degraded.assert_not_called()
