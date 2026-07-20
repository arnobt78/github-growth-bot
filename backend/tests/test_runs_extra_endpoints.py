from app.db import SessionLocal
from app.models import PipelineRun, Recommendation, StageRun


def _seed_run_with_stages():
    db = SessionLocal()
    run = PipelineRun(status="ok")
    db.add(run)
    db.commit()
    db.refresh(run)
    run_id = run.id

    db.add(StageRun(pipeline_run_id=run_id, stage_name="extractor", status="ok", duration_ms=120))
    db.add(StageRun(pipeline_run_id=run_id, stage_name="synthesizer", status="error", duration_ms=45, error="LLM router exhausted"))
    db.commit()
    db.close()
    return run_id


def test_run_out_includes_timestamps(client):
    db = SessionLocal()
    db.add(PipelineRun(status="ok"))
    db.commit()
    db.close()

    resp = client.get("/runs")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert "started_at" in body[0]
    assert "finished_at" in body[0]


def test_run_stages_endpoint_returns_seeded_rows_in_order(client):
    run_id = _seed_run_with_stages()

    resp = client.get(f"/runs/{run_id}/stages")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["stage_name"] == "extractor"
    assert body[0]["status"] == "ok"
    assert body[1]["stage_name"] == "synthesizer"
    assert body[1]["error"] == "LLM router exhausted"


def test_run_stages_returns_404_for_unknown_run(client):
    assert client.get("/runs/999999/stages").status_code == 404


def test_recommendation_out_includes_created_at(client):
    repo_resp = client.post("/repos", json={"owner": "octocat", "name": "hello-world"})
    repo_id = repo_resp.json()["id"]

    db = SessionLocal()
    db.add(Recommendation(
        repo_id=repo_id,
        category="missing_license",
        title="Add a LICENSE",
        body="No LICENSE file found.",
        validated=True,
    ))
    db.commit()
    db.close()

    resp = client.get("/recommendations")
    assert resp.status_code == 200
    assert "created_at" in resp.json()[0]
