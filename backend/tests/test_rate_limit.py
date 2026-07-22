def test_create_repo_rate_limited_after_threshold(client):
    from app.db import SessionLocal
    from app.models import User

    db = SessionLocal()
    user = db.query(User).filter(User.github_id == "12345").one()
    user.max_tracked_repos = 100
    db.commit()
    db.close()

    responses = [client.post("/repos", json={"owner": "octocat", "name": f"repo-{i}"}) for i in range(11)]
    statuses = [r.status_code for r in responses]
    assert 429 in statuses
