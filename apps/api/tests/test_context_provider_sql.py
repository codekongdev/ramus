"""B3 against the real schema: exact pinned versions (AC-17) and branch inheritance (AC-15, S2)."""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert, update

from ramus_api.modules.execution.application.ports import ContextProvider
from ramus_api.modules.resources.infrastructure.context_provider import build_context_provider
from ramus_api.orm_registry import metadata
from ramus_api.shared.infrastructure.database import Database

pytestmark = pytest.mark.integration

T = metadata.tables


@pytest.fixture
def ids(database: Database) -> Iterator[dict[str, UUID]]:
    """A project with parent/child/other conversations, one skill (v1, v2) and one saved result."""
    names = ["account", "project", "parent", "child", "other", "run", "task", "result", "rv1", "rv2"]
    ids = {name: uuid4() for name in names} | {"skill": uuid4(), "skill_v1": uuid4(), "skill_v2": uuid4()}
    ids |= {"text": uuid4(), "text_v1": uuid4()}
    with database.transaction() as s:
        s.execute(
            insert(T["account"]).values(
                id=ids["account"], email=f"{ids['account']}@example.test", display_name="민서"
            )
        )
        s.execute(insert(T["project"]).values(id=ids["project"], name="멤버십"))
        for name in ["parent", "child", "other"]:
            s.execute(
                insert(T["conversation"]).values(
                    id=ids[name],
                    project_id=ids["project"],
                    title=name,
                    origin="top",
                    created_by=ids["account"],
                )
            )
        s.execute(
            insert(T["run"]).values(
                id=ids["run"],
                project_id=ids["project"],
                conversation_id=ids["parent"],
                purpose="work",
                status="succeeded",
                requested_by=ids["account"],
                credential_account_id=ids["account"],
                input_snapshot={},
            )
        )
        s.execute(
            insert(T["task"]).values(
                id=ids["task"],
                source_conversation_id=ids["parent"],
                child_conversation_id=ids["child"],
                source_run_id=ids["run"],
                ordinal=1,
                title="조사",
                goal="조사",
                status="ready",
                requested_by=ids["account"],
            )
        )
        s.execute(
            insert(T["result"]).values(
                id=ids["result"],
                project_id=ids["project"],
                source_conversation_id=ids["child"],
                source_task_id=ids["task"],
                title="경쟁사 분석",
            )
        )
        for key, version in [("rv1", 1), ("rv2", 2)]:
            s.execute(
                insert(T["result_revision"]).values(
                    id=ids[key],
                    result_id=ids["result"],
                    version=version,
                    title="경쟁사 분석",
                    conclusion=f"결론 v{version}",
                    source={},
                    saved_by=ids["account"],
                )
            )
        s.execute(
            update(T["result"])
            .where(T["result"].c.id == ids["result"])
            .values(latest_revision_id=ids["rv2"], latest_version=2)
        )
        for resource, kind in [("skill", "skill"), ("text", "text")]:
            s.execute(
                insert(T["resource"]).values(
                    id=ids[resource],
                    project_id=ids["project"],
                    kind=kind,
                    latest_revision_id=ids[f"{resource}_v1"],
                    created_by=ids["account"],
                )
            )
        s.execute(
            insert(T["resource_revision"]).values(
                id=ids["skill_v1"],
                resource_id=ids["skill"],
                number=1,
                name="벤치마킹",
                description="",
                instructions="지침 v1",
                content_hash="1" * 64,
                created_by=ids["account"],
            )
        )
        s.execute(
            insert(T["resource_revision"]).values(
                id=ids["skill_v2"],
                resource_id=ids["skill"],
                number=2,
                name="벤치마킹",
                description="",
                instructions="지침 v2",
                content_hash="2" * 64,
                base_revision_id=ids["skill_v1"],
                created_by=ids["account"],
            )
        )
        s.execute(
            update(T["resource"])
            .where(T["resource"].c.id == ids["skill"])
            .values(latest_revision_id=ids["skill_v2"])
        )
        s.execute(
            insert(T["resource_revision"]).values(
                id=ids["text_v1"],
                resource_id=ids["text"],
                number=1,
                name="반품 정책",
                description="",
                content="14일 이내",
                content_hash="3" * 64,
                created_by=ids["account"],
            )
        )
    yield ids


def pin(database: Database, ids: dict, conversation: str, *revisions: tuple[str, str]) -> None:
    with database.transaction() as s:
        s.execute(
            T["conversation_resource"]
            .delete()
            .where(T["conversation_resource"].c.conversation_id == ids[conversation])
        )
        for resource, revision in revisions:
            s.execute(
                insert(T["conversation_resource"]).values(
                    conversation_id=ids[conversation],
                    resource_id=ids[resource],
                    revision_id=ids[revision],
                    applied_by=ids["account"],
                )
            )


def receive(database: Database, ids: dict, conversation: str, revision: str, version: int) -> None:
    with database.transaction() as s:
        s.execute(
            insert(T["conversation_input"]).values(
                id=uuid4(),
                conversation_id=ids[conversation],
                result_id=ids["result"],
                result_revision_id=ids[revision],
                version=version,
                title_snapshot="경쟁사 분석",
                conclusion_snapshot=f"보낸 시점의 결론 v{version}",
                source_snapshot={},
                origin="share",
                created_by=ids["account"],
            )
        )


@pytest.fixture
def provider() -> ContextProvider:
    return build_context_provider()


def snapshot(database: Database, provider: ContextProvider, conversation: UUID):
    with database.transaction() as s:
        return provider.snapshot(s, conversation)


def test_snapshot_uses_the_pinned_version_not_the_latest(database, ids, provider) -> None:
    pin(database, ids, "parent", ("skill", "skill_v1"), ("text", "text_v1"))
    context = snapshot(database, provider, ids["parent"])
    by_name = {r.name: r for r in context.resources}
    assert (by_name["벤치마킹"].revision_id, by_name["벤치마킹"].instructions) == (ids["skill_v1"], "지침 v1")
    assert (by_name["반품 정책"].kind, by_name["반품 정책"].content) == ("text", "14일 이내")
    assert [r.name for r in context.resources] == ["반품 정책", "벤치마킹"]


def test_snapshot_reads_the_received_conclusion_snapshot(database, ids, provider) -> None:
    receive(database, ids, "parent", "rv1", 1)
    (result,) = snapshot(database, provider, ids["parent"]).results
    # The result's latest is v2, but the conversation received v1 and keeps reading that snapshot.
    assert (result.result_revision_id, result.version, result.conclusion) == (
        ids["rv1"],
        1,
        "보낸 시점의 결론 v1",
    )


def test_unknown_or_empty_conversation_has_an_empty_context(database, ids, provider) -> None:
    assert snapshot(database, provider, ids["other"]).resources == ()
    assert snapshot(database, provider, uuid4()).results == ()


def test_child_inherits_exact_versions_and_stays_put_when_the_parent_changes(database, ids, provider) -> None:
    pin(database, ids, "parent", ("skill", "skill_v1"))
    receive(database, ids, "parent", "rv1", 1)
    with database.transaction() as s:
        provider.copy_resources(s, ids["parent"], ids["child"])
    child = snapshot(database, provider, ids["child"])
    assert [r.revision_id for r in child.resources] == [ids["skill_v1"]]
    assert child.results == ()  # received conclusions are not inherited

    pin(database, ids, "parent", ("skill", "skill_v2"), ("text", "text_v1"))  # parent moves to v2 later
    assert [r.revision_id for r in snapshot(database, provider, ids["child"]).resources] == [ids["skill_v1"]]


def test_copy_replaces_existing_target_pins_and_empty_source_clears(database, ids, provider) -> None:
    pin(database, ids, "child", ("text", "text_v1"))
    pin(database, ids, "parent", ("skill", "skill_v2"))
    with database.transaction() as s:
        provider.copy_resources(s, ids["parent"], ids["child"])
    assert [r.revision_id for r in snapshot(database, provider, ids["child"]).resources] == [ids["skill_v2"]]
    with database.transaction() as s:
        provider.copy_resources(s, ids["other"], ids["child"])
    assert snapshot(database, provider, ids["child"]).resources == ()


def test_copy_rolls_back_with_the_callers_transaction(database, ids, provider) -> None:
    pin(database, ids, "parent", ("skill", "skill_v1"))
    with pytest.raises(RuntimeError), database.transaction() as s:
        provider.copy_resources(s, ids["parent"], ids["child"])
        raise RuntimeError("branch creation failed later in the same use case")
    assert snapshot(database, provider, ids["child"]).resources == ()
