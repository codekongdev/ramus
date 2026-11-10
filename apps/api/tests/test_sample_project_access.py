"""Prepared sample destinations stay shared without making login a seeding operation."""

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from time import monotonic, sleep
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest
from fastapi.testclient import TestClient
from login_flow import login, unique_email
from sqlalchemy import delete, func, insert, select, text, update

from ramus_api.main import create_app
from ramus_api.modules.access.fakes.services import FakeMailer
from ramus_api.modules.access.infrastructure.models import AccountRow, MembershipRow
from ramus_api.modules.access.public import ensure_example_author, grant_sample_followup_memberships
from ramus_api.modules.projects.infrastructure.models import ProjectRow
from ramus_api.modules.projects.public import (
    FOLLOWUP_SAMPLE_PROJECT_ID,
    FOLLOWUP_SAMPLE_SEED_KEY,
    SHARED_SAMPLE_PROJECT_ID,
    ensure_followup_sample_project,
    ensure_shared_sample_project,
    followup_sample_project_id,
    lock_sample_preparation,
)
from ramus_api.settings import Settings
from ramus_api.shared.infrastructure.database import Database


@pytest.fixture
def sample_database(fresh_database_url: str, run_alembic) -> Iterator[Database]:
    run_alembic(fresh_database_url, "upgrade", "head")
    database = Database(fresh_database_url)
    try:
        yield database
    finally:
        database.dispose()


def test_followup_sample_identity_is_stable_and_distinct() -> None:
    assert FOLLOWUP_SAMPLE_PROJECT_ID == uuid5(NAMESPACE_URL, FOLLOWUP_SAMPLE_SEED_KEY)
    assert FOLLOWUP_SAMPLE_PROJECT_ID != SHARED_SAMPLE_PROJECT_ID


def _wait_for_advisory_waiter(database: Database, mode: str) -> bool:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        with database.engine.connect() as observer:
            if observer.scalar(text(
                "SELECT EXISTS (SELECT 1 FROM pg_locks "
                "WHERE locktype = 'advisory' AND NOT granted AND mode = :mode "
                "AND database = (SELECT oid FROM pg_database WHERE datname = current_database()))"
            ), {"mode": mode}):
                return True
        sleep(0.01)
    return False


@pytest.mark.integration
def test_login_waits_for_uncommitted_sample_preparation_and_joins_followup(sample_database: Database) -> None:
    mailer = FakeMailer()
    settings = Settings(_env_file=None, database_url=sample_database.engine.url.render_as_string(hide_password=False))
    app = create_app(settings, mailer=mailer)
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=1) as pool:
        with sample_database.transaction() as preparation:
            lock_sample_preparation(preparation, exclusive=True)
            # Re-entering the shared lock in this exclusive-owning transaction must succeed.
            ensure_shared_sample_project(preparation)
            followup_id = ensure_followup_sample_project(preparation)
            future = pool.submit(login, client, mailer, unique_email("during-seed"))
            waited = _wait_for_advisory_waiter(sample_database, "ShareLock")
            completed_before_commit = future.done()
            grant_sample_followup_memberships(preparation, SHARED_SAMPLE_PROJECT_ID, followup_id)
        # Commit preparation before joining the login thread, including on a failed wait observation.
        response = future.result(timeout=10)
        assert waited and not completed_before_commit
        account_id = UUID(response.json()["account"]["id"])
        assert response.json()["default_project_id"] == str(SHARED_SAMPLE_PROJECT_ID)
        with sample_database.transaction() as session:
            memberships = session.scalars(select(MembershipRow.project_id).where(
                MembershipRow.account_id == account_id
            )).all()
            assert set(memberships) == {SHARED_SAMPLE_PROJECT_ID, FOLLOWUP_SAMPLE_PROJECT_ID}


@pytest.mark.integration
def test_followup_preparation_preserves_edits_and_grants_existing_members_once(sample_database: Database) -> None:
    account_id = uuid4()
    with sample_database.transaction() as session:
        shared_id = ensure_shared_sample_project(session)
        assert followup_sample_project_id(session) is None
        session.execute(insert(AccountRow).values(id=account_id, email="member@example.test", display_name="member"))
        session.execute(insert(MembershipRow).values(account_id=account_id, project_id=shared_id, role="editor"))
        followup_id = ensure_followup_sample_project(session)
        grant_sample_followup_memberships(session, shared_id, followup_id)
        session.execute(update(ProjectRow).where(ProjectRow.id == followup_id).values(name="팀이 바꾼 후속 이름"))
    with sample_database.transaction() as session:
        assert ensure_followup_sample_project(session) == followup_id
        grant_sample_followup_memberships(session, shared_id, followup_id)
        assert session.get(ProjectRow, followup_id).name == "팀이 바꾼 후속 이름"
        assert session.get(ProjectRow, followup_id).is_shared_sample is False
        assert session.scalar(select(func.count()).select_from(MembershipRow)) == 2


@pytest.mark.integration
def test_followup_identity_collision_never_overwrites_a_project(sample_database: Database) -> None:
    with sample_database.transaction() as session:
        session.execute(insert(ProjectRow).values(id=FOLLOWUP_SAMPLE_PROJECT_ID, name="기존 프로젝트"))
    with pytest.raises(RuntimeError, match="identity"):
        with sample_database.transaction() as session:
            ensure_followup_sample_project(session)
    with sample_database.transaction() as session:
        row = session.get(ProjectRow, FOLLOWUP_SAMPLE_PROJECT_ID)
        assert row.name == "기존 프로젝트"
        assert row.seed_key is None


@pytest.mark.integration
def test_logins_join_only_prepared_destinations_and_keep_the_default_project(sample_database: Database) -> None:
    mailer = FakeMailer()
    settings = Settings(_env_file=None, database_url=sample_database.engine.url.render_as_string(hide_password=False))
    app = create_app(settings, mailer=mailer)
    # One app owns one relay lifespan; each participant keeps a separate cookie jar.
    with TestClient(app) as existing, closing(TestClient(app)) as newcomer:
        email = unique_email("before-seed")
        first = login(existing, mailer, email).json()
        assert first["default_project_id"] == str(SHARED_SAMPLE_PROJECT_ID)
        assert [p["id"] for p in existing.get("/api/projects").json()["items"]] == [str(SHARED_SAMPLE_PROJECT_ID)]
        with sample_database.transaction() as session:
            followup_id = ensure_followup_sample_project(session)
            grant_sample_followup_memberships(session, SHARED_SAMPLE_PROJECT_ID, followup_id)
        second = login(newcomer, mailer, unique_email("after-seed")).json()
        assert second["default_project_id"] == first["default_project_id"]
        for client in (existing, newcomer):
            assert {p["id"] for p in client.get("/api/projects").json()["items"]} == {
                str(SHARED_SAMPLE_PROJECT_ID), str(followup_id),
            }
        # A subsequent fresh authentication repairs a missing optional membership without cloning.
        account_id = UUID(first["account"]["id"])
        with sample_database.transaction() as session:
            session.execute(delete(MembershipRow).where(
                MembershipRow.account_id == account_id, MembershipRow.project_id == followup_id
            ))
            session.execute(text("UPDATE email_code SET created_at = created_at - interval '61 seconds' WHERE email = :email"), {"email": email})
        assert login(existing, mailer, email).json()["account"] == first["account"]
        with sample_database.transaction() as session:
            assert session.scalar(select(func.count()).select_from(ProjectRow)) == 2
            assert session.scalar(select(func.count()).select_from(MembershipRow)) == 4


@pytest.mark.integration
def test_example_authors_are_idempotent_and_have_no_project_memberships(sample_database: Database) -> None:
    account_id = uuid4()
    with sample_database.transaction() as session:
        ensure_example_author(session, account_id, "researcher-a", "예시·조사 담당 A")
        ensure_example_author(session, account_id, "researcher-a", "예시·조사 담당 A")
        row = session.get(AccountRow, account_id)
        assert row.email == "researcher-a@sample.ramus.invalid"
        assert row.display_name == "예시·조사 담당 A"
        assert session.scalar(select(func.count()).select_from(MembershipRow)) == 0


@pytest.mark.integration
@pytest.mark.parametrize("collision", ["id", "email"])
def test_example_author_identity_collision_preserves_existing_accounts(sample_database: Database, collision: str) -> None:
    author_id = uuid4()
    existing_id = author_id if collision == "id" else uuid4()
    email = "person@example.test" if collision == "id" else "researcher-a@sample.ramus.invalid"
    with sample_database.transaction() as session:
        session.execute(insert(AccountRow).values(id=existing_id, email=email, display_name="기존 작성자"))
    with pytest.raises(RuntimeError, match="identity"):
        with sample_database.transaction() as session:
            ensure_example_author(session, author_id, "researcher-a", "예시·조사 담당 A")
    with sample_database.transaction() as session:
        assert session.get(AccountRow, existing_id).display_name == "기존 작성자"
        assert session.scalar(select(func.count()).select_from(AccountRow)) == 1
