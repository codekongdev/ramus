import pytest
from fastapi.testclient import TestClient

from ramus_api.main import create_app
from ramus_api.settings import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
def app(settings):
    instance = create_app(settings)
    instance.state.database.create_schema()
    instance.state.workspace.ensure_demo()
    return instance


@pytest.fixture
def client(app):
    with TestClient(app) as instance:
        yield instance
