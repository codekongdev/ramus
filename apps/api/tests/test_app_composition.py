"""Composition root tests that need no database."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ramus_api import main
from ramus_api.container import AppContainer
from ramus_api.modules import system
from ramus_api.settings import Settings

UNREACHABLE_DATABASE_URL = "postgresql+psycopg://nobody:nothing@127.0.0.1:1/nowhere"


def test_create_app_does_not_connect_to_the_database() -> None:
    settings = Settings(_env_file=None, database_url=UNREACHABLE_DATABASE_URL)
    with TestClient(main.create_app(settings)) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_modules_are_registered_from_a_single_tuple() -> None:
    assert isinstance(main.MODULES, tuple)
    assert system.register in main.MODULES


def test_each_module_receives_the_shared_container(monkeypatch) -> None:
    received: list[tuple[FastAPI, AppContainer]] = []

    def spy(app: FastAPI, container: AppContainer) -> None:
        received.append((app, container))

    monkeypatch.setattr(main, "MODULES", (spy,))
    settings = Settings(_env_file=None, database_url=UNREACHABLE_DATABASE_URL)
    app = main.create_app(settings)
    [(registered_app, container)] = received
    assert registered_app is app
    assert container.settings is settings
    assert container.database is not None
    assert container.idempotency is not None


def test_module_level_app_exists() -> None:
    assert isinstance(main.app, FastAPI)
