from unittest.mock import patch


def test_trigger_run_returns_immediately_and_scopes_to_caller(client):
    client.post("/repos", json={"owner": "octocat", "name": "hello-world"})

    # Real pipeline execution depends on live GitHub/LLM calls whose latency
    # is out of this test's control (see app.pipeline.jobs.run_pipeline_for_all_repos).
    # Mocking it isolates what this test actually verifies: the request handler
    # schedules the run as a BackgroundTask rather than awaiting it inline.
    with patch("app.pipeline.jobs.run_pipeline_for_all_repos") as mock_run:
        resp = client.post("/runs")

    assert resp.status_code == 202
    assert resp.json() == {"status": "started"}
    assert mock_run.call_count == 1
    assert mock_run.call_args.kwargs["user_id"] == client.test_user_id


def test_trigger_run_requires_user_token(client_without_user_token):
    resp = client_without_user_token.post("/runs")
    assert resp.status_code == 401


def test_list_runs_exposes_pipeline_kind(client):
    client.post("/repos", json={"owner": "octocat", "name": "hello-world"})
    with patch("app.pipeline.jobs.run_pipeline_for_all_repos"):
        client.post("/runs")

    from app.db import SessionLocal
    from app.models import PipelineRun
    db = SessionLocal()
    db.query(PipelineRun).update({"status": "ok"})
    db.commit()
    db.close()

    resp = client.get("/runs")
    assert resp.status_code == 200
    assert all("pipeline_kind" in run for run in resp.json())
