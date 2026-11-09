"""A5 against PostgreSQL and the real executor; model/provider boundaries stay deterministic."""

import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest
from executor_harness import FAST, GatedLLM, run_row
from sqlalchemy import insert, update
from work_harness import (
    BRANCH_JSON,
    SqlTestWriter,
    WorkSeed,
    add_resource,
    request_work,
    rows,
    seed_work,
    work_rig,
)

from ramus_api.modules.conversations.domain.models import AuthorKind
from ramus_api.modules.conversations.infrastructure.repository import SqlConversationRepository
from ramus_api.modules.conversations.infrastructure.writer import SqlConversationWriter
from ramus_api.modules.execution.domain.models import RunPurpose, RunRequest
from ramus_api.modules.execution.fakes.connections import FakeAiConnectionQuery
from ramus_api.modules.execution.fakes.llm import FakeLLM
from ramus_api.modules.execution.infrastructure.branch_tasks import SqlBranchTaskStore
from ramus_api.modules.execution.infrastructure.run_store import SqlRunStore
from ramus_api.modules.execution.work_composition import build_work_execution_runtime
from ramus_api.modules.realtime.domain.events import EventName
from ramus_api.modules.realtime.fakes.publisher import FakeEventPublisher
from ramus_api.modules.resources.infrastructure.context_provider import build_context_provider
from ramus_api.modules.results.infrastructure.task_results import SqlTaskResultQuery
from ramus_api.orm_registry import metadata
from ramus_api.shared.domain.primitives import utc_now
from ramus_api.shared.infrastructure.database import Database

pytestmark = pytest.mark.integration


@pytest.fixture
def work_seed(database: Database) -> WorkSeed:
    return seed_work(database)


async def test_three_tasks_inherit_requester_and_run_to_ready_with_committed_events(
    database: Database, work_seed: WorkSeed
) -> None:
    rig = work_rig(database, work_seed)
    run_id, seq = request_work(database, rig, work_seed)
    assert await rig.runtime.worker.run_once()
    tasks = sorted(rows(database, "task", source_run_id=run_id), key=lambda item: item["ordinal"])
    assert [task["title"] for task in tasks] == ["가입", "혜택", "해지"]
    assert [task["ordinal"] for task in tasks] == [1, 2, 3]
    assert {task["status"] for task in tasks} == {"pending"}
    assert {task["requested_by"] for task in tasks} == {work_seed.owner}
    parent_messages = rows(database, "message", conversation_id=work_seed.parent)
    assert len(parent_messages) == 2
    notice = next(message for message in parent_messages if message["author_kind"] == "ai")
    assert notice["body"] == "별도 작업 3개로 나눠 진행합니다."
    assert run_row(database, run_id)["input_snapshot"]["message_to_seq"] == seq
    for task in tasks:
        child, = rows(database, "conversation", id=task["child_conversation_id"])
        assert (child["parent_id"], child["task_id"], child["created_by"], child["origin"]) == (
            work_seed.parent, task["id"], work_seed.owner, "branch"
        )
        child_run = run_row(database, task["current_run_id"])
        assert (child_run["requested_by"], child_run["credential_account_id"]) == (work_seed.owner, work_seed.owner)
        start, = rows(database, "message", conversation_id=child["id"])
        assert (start["author_kind"], start["run_id"], start["requested_by"]) == ("system", child_run["id"], work_seed.owner)
        assert start["body"] == f"{task['title']} 정책을 조사해줘"
    for _ in tasks:
        assert await rig.runtime.worker.run_once()
    assert not await rig.runtime.worker.run_once()
    assert len(rig.gateway.calls) == 4
    assert [call.is_child for call in rig.gateway.calls] == [False, True, True, True]
    assert {call.credential_account_id for call in rig.gateway.calls} == {work_seed.owner}
    for task in tasks:
        current, = rows(database, "task", id=task["id"])
        assert current["status"] == "ready"
        assert current["started_at"] is not None and current["finished_at"] is not None
        assert [event.data["task"]["status"] for event in rig.publisher.events if event.name == EventName.TASK_UPDATED and event.data["task"]["id"] == task["id"]] == ["pending", "running", "ready"]
    assert len([event for event in rig.publisher.events if event.name == EventName.CONVERSATION_CREATED]) == 3
    assert len([event for event in rig.publisher.events if event.name == EventName.MESSAGE_CREATED]) == 8


async def test_original_request_cutoff_excludes_later_messages_and_snapshots_actual_range(
    database: Database, work_seed: WorkSeed
) -> None:
    rig = work_rig(database, work_seed, FakeLLM())
    with database.transaction() as session:
        _, first = rig.writer.append(session, work_seed.parent, "먼저 논의한 내용", author_account_id=work_seed.other)
    run_id, requested_seq = request_work(database, rig, work_seed, body="@AI 방법을 알려줘")
    with database.transaction() as session:
        rig.writer.append(session, work_seed.parent, "LATER_MESSAGE_DO_NOT_EXECUTE", author_account_id=work_seed.other)
    assert await rig.runtime.worker.run_once()
    request, = rig.gateway.calls
    assert "LATER_MESSAGE_DO_NOT_EXECUTE" not in "\n".join(message.content for message in request.messages)
    assert request.messages[-1].content == "@AI 방법을 알려줘"
    assert run_row(database, run_id)["input_snapshot"] == {
        "message_from_seq": first, "message_to_seq": requested_seq,
        "resource_revision_ids": [], "input_result_revision_ids": [],
    }
    assert rows(database, "task", source_run_id=run_id) == []


async def test_exact_parent_revision_pins_are_initial_inheritance_and_never_follow_latest(
    database: Database, work_seed: WorkSeed
) -> None:
    resource_id, v1, v2 = add_resource(database, work_seed)
    rig = work_rig(database, work_seed)
    run_id, _ = request_work(database, rig, work_seed)
    assert await rig.runtime.worker.run_once()
    tasks = rows(database, "task", source_run_id=run_id)
    for task in tasks:
        pin, = rows(database, "conversation_resource", conversation_id=task["child_conversation_id"])
        assert (pin["resource_id"], pin["revision_id"]) == (resource_id, v1)
    pin = metadata.tables["conversation_resource"]
    with database.transaction() as session:
        session.execute(update(pin).where(pin.c.conversation_id == work_seed.parent).values(revision_id=v2))
    for _ in tasks:
        assert await rig.runtime.worker.run_once()
    assert rig.gateway.calls[0].context.resources[0].revision_id == v1
    for request in rig.gateway.calls[1:]:
        assert request.context.resources[0].revision_id == v1
        assert request.context.resources[0].instructions == "v1 지침"
    for task in tasks:
        child_run = run_row(database, task["current_run_id"])
        assert child_run["input_snapshot"]["resource_revision_ids"] == [str(v1)]


async def test_child_rejects_recursive_branch_and_syncs_failed_then_retried_task(
    database: Database, work_seed: WorkSeed
) -> None:
    gateway = FakeLLM(work_json=BRANCH_JSON, child_work_json=BRANCH_JSON)
    rig = work_rig(database, work_seed, gateway)
    run_id, _ = request_work(database, rig, work_seed)
    assert await rig.runtime.worker.run_once()
    tasks = rows(database, "task", source_run_id=run_id)
    for _ in tasks:
        assert await rig.runtime.worker.run_once()
    for task in tasks:
        current, = rows(database, "task", id=task["id"])
        assert (current["status"], current["error_code"]) == ("failed", "LLM_OUTPUT_INVALID")
        assert rows(database, "task", source_conversation_id=task["child_conversation_id"]) == []
        assert len(rows(database, "message", conversation_id=task["child_conversation_id"])) == 1
    target = tasks[0]
    with database.transaction() as session:
        rig.runtime.control.retry(session, target["current_run_id"], work_seed.owner)
    current, = rows(database, "task", id=target["id"])
    assert (current["status"], current["error_code"], current["finished_at"]) == ("pending", None, None)
    # A cancelled pending child updates Task without calling the purpose handler.
    with database.transaction() as session:
        rig.runtime.control.cancel(session, target["current_run_id"], work_seed.owner)
    await rig.runtime.relay.flush()
    current, = rows(database, "task", id=target["id"])
    assert current["status"] == "cancelled" and current["finished_at"] is not None


async def test_branch_failure_rolls_back_every_child_pin_run_message_and_event_then_retry_is_unique(
    database: Database, work_seed: WorkSeed
) -> None:
    add_resource(database, work_seed)
    rig = work_rig(database, work_seed)
    rig.contexts.fail_copy = 2
    run_id, _ = request_work(database, rig, work_seed)
    assert await rig.runtime.worker.run_once()
    assert run_row(database, run_id)["status"] == "failed"
    assert rows(database, "task", source_run_id=run_id) == []
    assert rows(database, "conversation", parent_id=work_seed.parent) == []
    assert len(rows(database, "message", conversation_id=work_seed.parent)) == 1
    project_runs = rows(database, "run", project_id=work_seed.project)
    assert [run["id"] for run in project_runs] == [run_id]
    assert {event.name for event in rig.publisher.events} == {EventName.MESSAGE_CREATED, EventName.RUN_UPDATED}
    assert all(event.data["run"]["id"] == run_id for event in rig.publisher.events if event.name == EventName.RUN_UPDATED)
    rig.contexts.fail_copy = None
    with database.transaction() as session:
        rig.runtime.control.retry(session, run_id, work_seed.owner)
    assert await rig.runtime.worker.run_once()
    assert run_row(database, run_id)["status"] == "succeeded"
    assert len(rows(database, "task", source_run_id=run_id)) == 3
    assert len(rows(database, "conversation", parent_id=work_seed.parent)) == 3
    assert len(rows(database, "message", conversation_id=work_seed.parent)) == 2
    assert len([event for event in rig.publisher.events if event.name == EventName.CONVERSATION_CREATED]) == 3


async def test_cancelled_parent_discards_late_branch_without_creating_tasks(
    database: Database, work_seed: WorkSeed
) -> None:
    gateway = GatedLLM(FakeLLM(work_json=BRANCH_JSON))
    rig = work_rig(database, work_seed, gateway)
    run_id, _ = request_work(database, rig, work_seed)
    running = asyncio.create_task(rig.runtime.worker.run_once())
    await asyncio.wait_for(gateway.started.wait(), 5)
    with database.transaction() as session:
        rig.runtime.control.cancel(session, run_id, work_seed.owner)
    gateway.release.set()
    assert await asyncio.wait_for(running, 5)
    assert run_row(database, run_id)["status"] == "cancelled"
    assert rows(database, "task", source_run_id=run_id) == []
    assert rows(database, "conversation", parent_id=work_seed.parent) == []
    assert len(rows(database, "message", conversation_id=work_seed.parent)) == 1
    assert not any(event.name in (EventName.TASK_UPDATED, EventName.CONVERSATION_CREATED) for event in rig.publisher.events)


async def test_all_siblings_keep_one_pin_set_when_parent_changes_between_child_copies(
    database: Database, work_seed: WorkSeed
) -> None:
    _, v1, v2 = add_resource(database, work_seed)
    rig = work_rig(database, work_seed)
    pin = metadata.tables["conversation_resource"]

    def change_parent_after_first_copy(number: int) -> None:
        if number == 1:
            # Simulates B1's independently committed application while the branch transaction is open.
            with database.transaction() as session:
                session.execute(update(pin).where(pin.c.conversation_id == work_seed.parent).values(revision_id=v2))

    rig.contexts.after_copy = change_parent_after_first_copy
    run_id, _ = request_work(database, rig, work_seed)
    assert await rig.runtime.worker.run_once()
    parent_pin, = rows(database, "conversation_resource", conversation_id=work_seed.parent)
    assert parent_pin["revision_id"] == v2
    tasks = rows(database, "task", source_run_id=run_id)
    assert len(tasks) == 3
    for task in tasks:
        child_pin, = rows(database, "conversation_resource", conversation_id=task["child_conversation_id"])
        assert child_pin["revision_id"] == v1


async def test_summary_and_late_previous_run_cannot_replace_current_task_state(
    database: Database, work_seed: WorkSeed
) -> None:
    rig = work_rig(database, work_seed)
    parent_run, _ = request_work(database, rig, work_seed)
    assert await rig.runtime.worker.run_once()
    tasks = rows(database, "task", source_run_id=parent_run)
    for _ in tasks:
        assert await rig.runtime.worker.run_once()
    target = tasks[0]
    store, projector = SqlRunStore(), SqlBranchTaskStore(SqlTaskResultQuery())
    with database.transaction() as session:
        old_run = store.lock(session, target["current_run_id"])
        assert old_run is not None
    new_run_id, _ = request_work(
        database, rig, work_seed, conversation_id=target["child_conversation_id"], task_id=target["id"],
        body="@AI 이 작업의 예외도 보완해줘",
    )
    with database.transaction() as session:
        assert projector.project(session, old_run, utc_now()) is None
        # Summary runs can coexist with work; their completion must not mark its Task ready.
        assert projector.project(session, replace(old_run, purpose=RunPurpose.SUMMARY), utc_now()) is None
    current, = rows(database, "task", id=target["id"])
    assert (current["current_run_id"], current["status"]) == (new_run_id, "pending")
    assert await rig.runtime.worker.run_once()
    current, = rows(database, "task", id=target["id"])
    assert (current["current_run_id"], current["status"]) == (new_run_id, "ready")
    assert len(rows(database, "task", source_run_id=parent_run)) == 3


async def test_child_model_receives_goal_that_is_absent_from_start_input(
    database: Database, work_seed: WorkSeed
) -> None:
    rig = work_rig(database, work_seed)
    run_id, _ = request_work(database, rig, work_seed)
    assert await rig.runtime.worker.run_once()
    tasks = rows(database, "task", source_run_id=run_id)
    for _ in tasks:
        assert await rig.runtime.worker.run_once()
    expected_goals = {task["goal"] for task in tasks}
    observed_goals = {
        message.content.removeprefix("작업 목표:\n")
        for call in rig.gateway.calls[1:]
        for message in call.messages
        if message.content.startswith("작업 목표:\n")
    }
    assert observed_goals == expected_goals
    for task in tasks:
        start = next(
            message for message in rows(database, "message", conversation_id=task["child_conversation_id"])
            if message["author_kind"] == "system"
        )
        assert task["goal"] not in start["body"]


async def test_task_events_preserve_existing_result_id_on_followup_work_and_cancel(
    database: Database, work_seed: WorkSeed
) -> None:
    rig = work_rig(database, work_seed)
    parent_run, _ = request_work(database, rig, work_seed)
    assert await rig.runtime.worker.run_once()
    tasks = rows(database, "task", source_run_id=parent_run)
    for _ in tasks:
        assert await rig.runtime.worker.run_once()
    target, result_id = tasks[0], uuid4()
    with database.transaction() as session:
        session.execute(
            insert(metadata.tables["result"]).values(
                id=result_id, project_id=work_seed.project, source_conversation_id=target["child_conversation_id"],
                source_task_id=target["id"], title="검토 중인 결과",
            )
        )
    before = len(rig.publisher.events)
    followup, _ = request_work(
        database, rig, work_seed, conversation_id=target["child_conversation_id"], task_id=target["id"],
        body="@AI 근거를 추가해줘",
    )
    with database.transaction() as session:
        rig.runtime.control.cancel(session, followup, work_seed.owner)
    await rig.runtime.relay.flush()
    task_events = [
        event.data["task"] for event in rig.publisher.events[before:]
        if event.name == EventName.TASK_UPDATED and event.data["task"]["id"] == target["id"]
    ]
    assert [(event["status"], event["result_id"]) for event in task_events] == [
        ("pending", result_id), ("cancelled", result_id),
    ]


async def test_real_conversation_writer_and_context_provider_complete_branch_flow(
    database: Database, work_seed: WorkSeed
) -> None:
    _, v1, _ = add_resource(database, work_seed)
    repository, events = SqlConversationRepository(), SqlTestWriter()
    publisher, gateway = FakeEventPublisher(), FakeLLM(work_json=BRANCH_JSON)
    runtime = build_work_execution_runtime(
        transaction=database.transaction, publisher=publisher, gateway=gateway,
        context_provider=build_context_provider(), connections=FakeAiConnectionQuery({work_seed.owner}),
        writer=SqlConversationWriter(repository, events), config=FAST,
    )
    events.relay = runtime.relay
    with database.transaction() as session:
        run = runtime.requester.request(
            session, RunRequest(work_seed.project, work_seed.parent, None, RunPurpose.WORK, None, work_seed.owner)
        )
        message = repository.append_message(
            session, work_seed.parent, "@AI 가입·혜택·해지를 나눠 조사해줘", AuthorKind.HUMAN,
            author_account_id=work_seed.owner, requested_by=work_seed.owner, run_id=run.run_id,
        )
    assert await runtime.worker.run_once()
    tasks = rows(database, "task", source_run_id=run.run_id)
    assert len(tasks) == 3
    for _ in tasks:
        assert await runtime.worker.run_once()
    assert not await runtime.worker.run_once()
    assert {row["status"] for row in rows(database, "task", source_run_id=run.run_id)} == {"ready"}
    assert run_row(database, run.run_id)["input_snapshot"]["message_to_seq"] == message.seq
    for task in tasks:
        start, answer = sorted(
            rows(database, "message", conversation_id=task["child_conversation_id"]), key=lambda row: row["seq"]
        )
        assert (start["author_kind"], answer["author_kind"]) == ("system", "ai")
        pin, = rows(database, "conversation_resource", conversation_id=task["child_conversation_id"])
        assert pin["revision_id"] == v1
    assert {call.context.resources[0].revision_id for call in gateway.calls} == {v1}
    created = [event for event in publisher.events if event.name == EventName.CONVERSATION_CREATED]
    assert len(created) == 3
    assert {tuple(event.data["conversation"]["path"]) for event in created} == {("멤버십",)}
