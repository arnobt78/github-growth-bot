from app.db import SessionLocal
from app.models import Draft, Repo
from app.pipeline.content.assembler import ContentAssembler
from app.pipeline.content_base import ContentPipelineContext, ContentTask


def _db_and_repo(user_id: int):
    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world", user_id=user_id)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return db, repo


def test_assembler_writes_draft_per_valid_task(seed_user):
    db, repo = _db_and_repo(seed_user)
    ctx = ContentPipelineContext(repo=repo)
    ctx.tasks = [
        ContentTask(kind="readme_suggestion", target="readme", structured=False, current="# Old", winner="# New", winner_reason="clearer", valid=True),
        ContentTask(kind="missing_doc_suggestion", target="SECURITY.md", structured=False, current=None, winner="# Security Policy", winner_reason="standard template", valid=True),
        ContentTask(kind="topic_suggestion", target="topics", structured=True, current=["cli"], winner=["cli", "automation"], winner_reason="broader", valid=True),
        ContentTask(kind="seo_suggestion", target="description", structured=True, current="old desc", winner={"description": "new desc", "keywords": ["cli", "automation"]}, winner_reason="sharper", valid=True),
        ContentTask(kind="readme_suggestion", target="readme", structured=False, current="# Old", winner=None, winner_reason=None, valid=False),
    ]

    ctx = ContentAssembler(db_session=db).run(ctx)

    drafts = db.query(Draft).filter_by(repo_id=repo.id).all()
    assert len(drafts) == 4

    readme_draft = next(d for d in drafts if d.kind == "readme_suggestion")
    assert readme_draft.content == {"current": "# Old", "suggested": "# New", "reason": "clearer"}
    assert readme_draft.status == "pending"

    doc_draft = next(d for d in drafts if d.kind == "missing_doc_suggestion")
    assert doc_draft.target == "SECURITY.md"
    assert doc_draft.content == {"suggested": "# Security Policy", "reason": "standard template"}

    topic_draft = next(d for d in drafts if d.kind == "topic_suggestion")
    assert topic_draft.content == {"current": ["cli"], "suggested": ["cli", "automation"], "reason": "broader"}

    seo_draft = next(d for d in drafts if d.kind == "seo_suggestion")
    assert seo_draft.content == {"current": "old desc", "suggested_description": "new desc", "keywords": ["cli", "automation"], "reason": "sharper"}

    db.close()


def test_assembler_skips_invalid_tasks(seed_user):
    db, repo = _db_and_repo(seed_user)
    ctx = ContentPipelineContext(repo=repo)
    ctx.tasks = [ContentTask(kind="readme_suggestion", target="readme", structured=False, current=None, valid=False)]

    ctx = ContentAssembler(db_session=db).run(ctx)

    assert db.query(Draft).filter_by(repo_id=repo.id).count() == 0
    db.close()


def test_assembler_writes_release_notes_draft_and_advances_last_release_tag(seed_user):
    db, repo = _db_and_repo(seed_user)
    ctx = ContentPipelineContext(repo=repo)
    ctx.tasks = [
        ContentTask(kind="release_notes", target="v1.2.0", structured=False, current=None, winner="## Features\n- Dark mode", winner_reason="clear and accurate", valid=True),
    ]

    ctx = ContentAssembler(db_session=db).run(ctx)

    draft = db.query(Draft).filter_by(repo_id=repo.id, kind="release_notes").one()
    assert draft.target == "v1.2.0"
    assert draft.content == {"suggested": "## Features\n- Dark mode", "reason": "clear and accurate"}

    db.refresh(repo)
    assert repo.last_release_tag == "v1.2.0"
    db.close()


def test_assembler_does_not_advance_last_release_tag_for_invalid_task(seed_user):
    db, repo = _db_and_repo(seed_user)
    ctx = ContentPipelineContext(repo=repo)
    ctx.tasks = [
        ContentTask(kind="release_notes", target="v1.2.0", structured=False, current=None, winner=None, winner_reason=None, valid=False),
    ]

    ctx = ContentAssembler(db_session=db).run(ctx)

    assert db.query(Draft).filter_by(repo_id=repo.id, kind="release_notes").count() == 0
    db.refresh(repo)
    assert repo.last_release_tag is None
    db.close()
