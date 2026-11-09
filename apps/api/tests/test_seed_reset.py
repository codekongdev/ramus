"""Operator maintenance is atomic, explicit, scoped, and exercised only on temporary databases."""

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import uuid4

import pytest
from sqlalchemy import insert, update
from test_seed import CONTENT_MARKER_KEY, ROOT, snapshot

from ramus_api.modules.access.infrastructure.models import (
    AccountRow,
    AIConnectionRow,
    MembershipRow,
    SessionRow,
)
from ramus_api.modules.conversations.infrastructure.models import ConversationRow, MessageRow
from ramus_api.modules.execution.infrastructure.models import RunRow
from ramus_api.modules.projects.infrastructure.models import ProjectRow
from ramus_api.modules.projects.public import FOLLOWUP_SAMPLE_PROJECT_ID, SHARED_SAMPLE_PROJECT_ID
from ramus_api.modules.resources.domain.models import ResourceKind
from ramus_api.modules.resources.domain.rules import content_hash, normalize_content
from ramus_api.modules.resources.infrastructure.models import (
    ConversationResourceRow,
    ResourceRevisionRow,
    ResourceRow,
)
from ramus_api.modules.results.infrastructure.models import ResultDraftRow, ResultRevisionRow, ResultRow
from ramus_api.modules.seed.domain.content import sample_id
from ramus_api.modules.seed.infrastructure.models import SeedMarkerRow
from ramus_api.modules.seed.infrastructure.sample import SHARED_SAMPLE_MARKER_KEY, prepare_shared_sample
from ramus_api.modules.sharing.infrastructure.models import ConversationInputRow
from ramus_api.shared.infrastructure.database import Database
from ramus_api.shared.infrastructure.receipts import RequestReceiptRow

pytestmark = pytest.mark.integration


@pytest.fixture
def seeded_database(fresh_database_url: str, run_alembic) -> Iterator[Database]:
    run_alembic(fresh_database_url, "upgrade", "head")
    database = Database(fresh_database_url)
    try:
        prepare_shared_sample(database)
        yield database
    finally:
        database.dispose()


def reset_cli(database: Database, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ramus_api.modules.seed", *arguments],
        env={**os.environ, "DATABASE_URL": database.engine.url.render_as_string(hide_password=False)},
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


@pytest.mark.parametrize("arguments", [
    ("--reset",),
    ("--reset", "--work-preserved"),
    ("--reset", "--confirm-project-id", str(SHARED_SAMPLE_PROJECT_ID)),
    ("--confirm-project-id", str(SHARED_SAMPLE_PROJECT_ID), "--work-preserved"),
    ("--reset", "--confirm-project-id", str(FOLLOWUP_SAMPLE_PROJECT_ID), "--work-preserved"),
])
def test_reset_cli_rejects_missing_confirmation_or_wrong_project_without_changes(
    seeded_database: Database, arguments: tuple[str, ...]
) -> None:
    before = snapshot(seeded_database.engine)
    result = reset_cli(seeded_database, *arguments)
    assert result.returncode != 0
    assert result.stderr.strip()
    assert snapshot(seeded_database.engine) == before


@pytest.mark.parametrize("status", ["pending", "running"])
@pytest.mark.parametrize("project_id", [SHARED_SAMPLE_PROJECT_ID, FOLLOWUP_SAMPLE_PROJECT_ID])
def test_reset_refuses_active_runs_in_either_sample_project(
    seeded_database: Database, status: str, project_id
) -> None:
    with seeded_database.transaction() as session:
        if project_id == SHARED_SAMPLE_PROJECT_ID:
            session.execute(update(RunRow).where(RunRow.id == sample_id("run:mall-a")).values(status=status))
        else:
            conversation_id = uuid4()
            session.execute(insert(ConversationRow).values(
                id=conversation_id, project_id=project_id, title="후속 실행 중 대화", origin="top",
                created_by=sample_id("author:leader"),
            ))
            session.execute(insert(RunRow).values(
                id=uuid4(), project_id=project_id, conversation_id=conversation_id, purpose="work",
                status=status, requested_by=sample_id("author:leader"),
                credential_account_id=sample_id("author:leader"), input_snapshot={},
            ))
    before = snapshot(seeded_database.engine)
    with pytest.raises(RuntimeError, match="pending or running"):
        prepare_shared_sample(seeded_database, reset_project_id=SHARED_SAMPLE_PROJECT_ID, work_preserved=True)
    assert snapshot(seeded_database.engine) == before


def _receipt(identifier, actor_id, scope, response) -> dict:
    return {
        "id": identifier, "actor_id": str(actor_id), "scope": scope,
        "idempotency_key": str(identifier), "fingerprint": "0" * 64, "response": response,
        "created_at": datetime.now(UTC),
    }


def test_reset_recreates_samples_and_removes_work_receipts_while_preserving_accounts_and_other_projects(
    seeded_database: Database,
) -> None:
    database = seeded_database
    user_id, session_id, other_project_id, other_conversation_id = (uuid4() for _ in range(4))
    followup_conversation_id, message_id, revision_id, run_id, result_revision_id = (uuid4() for _ in range(5))
    work_receipt_id, resource_receipt_id, unaffected_receipt_id = (uuid4() for _ in range(3))
    now = datetime.now(UTC)
    with database.transaction() as session:
        session.execute(insert(AccountRow).values(id=user_id, email="operator-test@example.test", display_name="실제 팀원"))
        session.execute(insert(SessionRow).values(
            id=session_id, account_id=user_id, token_hash="synthetic-session-hash", expires_at=now + timedelta(days=1),
        ))
        session.execute(insert(AIConnectionRow).values(
            account_id=user_id, provider="openai", ciphertext="synthetic-test-ciphertext", status="connected",
            verified_at=now,
        ))
        session.execute(insert(ProjectRow).values(id=other_project_id, name="보존 대상 프로젝트"))
        for project_id in (SHARED_SAMPLE_PROJECT_ID, FOLLOWUP_SAMPLE_PROJECT_ID, other_project_id):
            session.execute(insert(MembershipRow).values(account_id=user_id, project_id=project_id, role="editor"))
        for identifier, project_id, title in (
            (other_conversation_id, other_project_id, "보존할 대화"),
            (followup_conversation_id, FOLLOWUP_SAMPLE_PROJECT_ID, "초기화할 후속 대화"),
        ):
            session.execute(insert(ConversationRow).values(
                id=identifier, project_id=project_id, title=title, origin="top", created_by=user_id,
            ))
        session.execute(insert(MessageRow).values(
            id=message_id, conversation_id=sample_id("conversation:design"), author_kind="human",
            author_account_id=user_id, body="초기화 전 팀원이 만든 논의",
        ))
        session.execute(insert(MessageRow).values(
            id=uuid4(), conversation_id=other_conversation_id, author_kind="human",
            author_account_id=user_id, body="다른 프로젝트에서 보존할 메시지",
        ))
        resource_id = sample_id("resource:benchmark-skill")
        content = normalize_content(ResourceKind.SKILL, name="수정된 조사 스킬", description="팀의 수정",
                                    instructions="실제 논의에서 추가한 조사 기준", content=None, file_name=None)
        session.execute(insert(ResourceRevisionRow).values(
            id=revision_id, resource_id=resource_id, number=2, name=content.name, description=content.description,
            instructions=content.instructions, content_hash=content_hash(content),
            base_revision_id=sample_id("resource:benchmark-skill:v1"), created_by=user_id,
        ))
        session.execute(update(ResourceRow).where(ResourceRow.id == resource_id).values(latest_revision_id=revision_id))
        result_id = sample_id("result:mall-a")
        original = session.get(ResultRevisionRow, sample_id("result:mall-a:v1"))
        session.execute(insert(ResultRevisionRow).values(
            id=result_revision_id, result_id=result_id, version=2, title="팀에서 수정한 결론",
            conclusion="실제 참여자가 보완한 결론입니다.", source=original.source, saved_by=user_id,
        ))
        session.execute(update(ResultRow).where(ResultRow.id == result_id).values(
            latest_revision_id=result_revision_id, latest_version=2,
        ))
        session.execute(insert(RunRow).values(
            id=run_id, project_id=SHARED_SAMPLE_PROJECT_ID, conversation_id=sample_id("conversation:mall-a"),
            purpose="summary", target_id=result_id, status="succeeded", requested_by=user_id,
            credential_account_id=user_id, input_snapshot={},
        ))
        session.execute(insert(ResultDraftRow).values(
            result_id=result_id, status="ready", conclusion="검토 중인 결과 초안", base_version=2, run_id=run_id,
            message_from_seq=original.source["message_from_seq"], message_to_seq=original.source["message_to_seq"],
        ))
        for values in (
            _receipt(work_receipt_id, user_id, f"message:{sample_id('conversation:design')}", {"message_id": str(message_id)}),
            _receipt(resource_receipt_id, user_id, "resource.revision", {"revision": {"id": str(revision_id)}}),
            _receipt(unaffected_receipt_id, user_id, "auth.verify", {"account_id": str(user_id)}),
        ):
            session.execute(insert(RequestReceiptRow).values(**values))
    before = snapshot(database.engine)
    result = reset_cli(database, "--reset", "--confirm-project-id", str(SHARED_SAMPLE_PROJECT_ID), "--work-preserved")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"project_id": str(SHARED_SAMPLE_PROJECT_ID)}
    after = snapshot(database.engine)
    for name in ("account", "session", "ai_connection", "membership", "project"):
        assert after[name] == before[name]
    assert [row for row in after["conversation"] if row["project_id"] == other_project_id] == [
        row for row in before["conversation"] if row["project_id"] == other_project_id
    ]
    assert [row for row in after["message"] if row["conversation_id"] == other_conversation_id] == [
        row for row in before["message"] if row["conversation_id"] == other_conversation_id
    ]
    assert followup_conversation_id not in {row["id"] for row in after["conversation"]}
    assert message_id not in {row["id"] for row in after["message"]}
    assert revision_id not in {row["id"] for row in after["resource_revision"]}
    assert result_revision_id not in {row["id"] for row in after["result_revision"]}
    assert run_id not in {row["id"] for row in after["run"]}
    assert after["result_draft"] == []
    assert {row["id"] for row in after["request_receipt"]} == {unaffected_receipt_id}
    assert len(after["conversation"]) == 5
    assert len(after["resource_revision"]) == len(after["result_revision"]) == 3
    assert {row["status"] for row in after["run"]} == {"succeeded"}
    assert {row["version"] for row in after["seed_marker"]} == {1}
    prepare_shared_sample(database)
    assert snapshot(database.engine) == after


def test_reset_refuses_external_result_references_and_rolls_back_all_changes(seeded_database: Database) -> None:
    project_id, conversation_id = uuid4(), uuid4()
    author_id = sample_id("author:leader")
    with seeded_database.transaction() as session:
        session.execute(insert(ProjectRow).values(id=project_id, name="외부 프로젝트"))
        session.execute(insert(ConversationRow).values(
            id=conversation_id, project_id=project_id, title="예시 결과를 사용하는 외부 대화",
            origin="top", created_by=author_id,
        ))
        source = session.get(ResultRevisionRow, sample_id("result:mall-a:v1"))
        session.execute(insert(ConversationInputRow).values(
            id=uuid4(), conversation_id=conversation_id, result_id=source.result_id, result_revision_id=source.id,
            version=source.version, title_snapshot=source.title, conclusion_snapshot=source.conclusion,
            source_snapshot=source.source, origin="share", created_by=author_id,
        ))
    before = snapshot(seeded_database.engine)
    with pytest.raises(RuntimeError, match="another project uses sample conclusions"):
        prepare_shared_sample(seeded_database, reset_project_id=SHARED_SAMPLE_PROJECT_ID, work_preserved=True)
    assert snapshot(seeded_database.engine) == before


def test_reset_nowait_refuses_an_existing_writer_without_changes(seeded_database: Database) -> None:
    before = snapshot(seeded_database.engine)
    # This independently owned connection keeps PostgreSQL's write lock until the context exits.
    with seeded_database.engine.connect() as writer, writer.begin():
        writer.execute(update(ProjectRow).where(ProjectRow.id == SHARED_SAMPLE_PROJECT_ID).values(name=ProjectRow.name))
        started = monotonic()
        result = reset_cli(
            seeded_database, "--reset", "--confirm-project-id", str(SHARED_SAMPLE_PROJECT_ID), "--work-preserved",
        )
        elapsed = monotonic() - started
        assert result.returncode != 0
        assert "database is in use" in result.stderr
        assert elapsed < 5, "NOWAIT reset should fail promptly while the writer still holds its lock"
        assert snapshot(seeded_database.engine) == before
    assert snapshot(seeded_database.engine) == before


def test_reset_refuses_external_resource_pins_and_rolls_back_all_changes(seeded_database: Database) -> None:
    project_id, conversation_id = uuid4(), uuid4()
    author_id = sample_id("author:leader")
    with seeded_database.transaction() as session:
        session.execute(insert(ProjectRow).values(id=project_id, name="자료를 사용하는 외부 프로젝트"))
        session.execute(insert(ConversationRow).values(
            id=conversation_id, project_id=project_id, title="샘플 스킬을 사용하는 외부 대화",
            origin="top", created_by=author_id,
        ))
        session.execute(insert(ConversationResourceRow).values(
            conversation_id=conversation_id, resource_id=sample_id("resource:benchmark-skill"),
            revision_id=sample_id("resource:benchmark-skill:v1"), applied_by=author_id,
        ))
    before = snapshot(seeded_database.engine)
    with pytest.raises(RuntimeError, match="another project references sample resources"):
        prepare_shared_sample(seeded_database, reset_project_id=SHARED_SAMPLE_PROJECT_ID, work_preserved=True)
    assert snapshot(seeded_database.engine) == before


@pytest.mark.parametrize("marker_key", [SHARED_SAMPLE_MARKER_KEY, CONTENT_MARKER_KEY])
def test_unknown_seed_marker_version_is_rejected_without_changes(seeded_database: Database, marker_key: str) -> None:
    with seeded_database.transaction() as session:
        session.execute(update(SeedMarkerRow).where(SeedMarkerRow.key == marker_key).values(version=999))
    before = snapshot(seeded_database.engine)
    with pytest.raises(RuntimeError, match="explicit migration"):
        prepare_shared_sample(seeded_database)
    assert snapshot(seeded_database.engine) == before
