import os
import pytest
import tempfile

# Create a temporary directory for test databases
_test_db_dir = tempfile.mkdtemp()
_test_db_path = os.path.join(_test_db_dir, "test.db")

os.environ.setdefault("DATABASE_URL", f"sqlite:///{_test_db_path}")
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("GITHUB_TOKEN", "test-token")


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    test_client = TestClient(app)
    test_client.headers.update({"Authorization": "Bearer test-key"})
    return test_client


@pytest.fixture
def client_without_auth():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_db():
    from app.db import Base, engine
    import app.models  # noqa: F401
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
