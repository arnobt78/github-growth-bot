from app.db import Base, engine, SessionLocal
from app.models import Repo


def test_create_and_query_repo():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world")
    db.add(repo)
    db.commit()

    fetched = db.query(Repo).filter_by(owner="octocat", name="hello-world").first()
    assert fetched is not None
    assert fetched.name == "hello-world"
    assert fetched.tracked_since is not None
    db.close()
