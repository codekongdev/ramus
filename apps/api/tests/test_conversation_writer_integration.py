"""Public SQL writer atomicity and cursor safety against a disposable PostgreSQL database."""

import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Event
from uuid import uuid4

import pytest
from executor_harness import seed_rows
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from ramus_api.main import create_app
from ramus_api.modules.conversations.composition import CommittedEvents
from ramus_api.modules.conversations.domain.models import AuthorKind, NewChildConversation, NewMessage
from ramus_api.modules.conversations.infrastructure.models import ConversationRow, MessageRow
from ramus_api.modules.conversations.infrastructure.repository import SqlConversationRepository
from ramus_api.modules.conversations.infrastructure.writer import SqlConversationWriter
from ramus_api.modules.execution.infrastructure.models import RunRow, TaskRow
from ramus_api.modules.realtime.domain.events import EventName

pytestmark = pytest.mark.integration


@pytest.fixture
def writer_workspace(integration_settings):
    container = create_app(integration_settings).state.container
    seed = seed_rows(container.database)
    repository = SqlConversationRepository()
    writer = SqlConversationWriter(repository, CommittedEvents(container))
    with container.database.transaction() as session:
        run_id = session.scalar(select(RunRow.id).where(RunRow.conversation_id == seed.conversations[0]))
    assert run_id is not None
    try:
        yield container, seed, run_id, repository, writer
    finally:
        container.events.close()
        container.database.dispose()


@pytest.mark.parametrize("author_kind", [AuthorKind.AI, AuthorKind.SYSTEM])
async def test_append_publishes_only_after_commit_and_nothing_after_rollback(writer_workspace, author_kind):
    container, seed, run_id, _, writer = writer_workspace
    conversation_id = seed.conversations[0]
    subscriber = container.events.subscribe(seed.project)
    request = NewMessage(conversation_id, author_kind, "AI 또는 시스템 본문", seed.owner, run_id)

    with pytest.raises(RuntimeError, match="roll back"):
        with container.database.transaction() as session:
            rolled_back_id = writer.append_message(session, request)
            assert await container.event_relay.flush() == 0
            raise RuntimeError("roll back")
    assert await container.event_relay.flush() == 0
    assert await subscriber.next(timeout=0.01) is None
    with container.database.transaction() as session:
        assert session.get(MessageRow, rolled_back_id) is None

    with container.database.transaction() as session:
        committed_id = writer.append_message(session, request)
        assert await container.event_relay.flush() == 0
    with container.database.transaction() as session:
        committed = session.get(MessageRow, committed_id)
        assert committed.author_kind == author_kind.value
        assert committed.author_account_id is None
        assert committed.requested_by == seed.owner
        assert committed.run_id == run_id
        seq = committed.seq
    assert await container.event_relay.flush() == 1
    event = await subscriber.next(timeout=0.1)
    assert event.name == EventName.MESSAGE_CREATED
    assert dict(event.data) == {
        "conversation_id": conversation_id, "message_id": committed_id, "seq": seq,
    }
    assert await container.event_relay.flush() == 0
    assert await subscriber.next(timeout=0.01) is None
    subscriber.close()


async def test_child_and_task_commit_together_with_path_and_one_event(writer_workspace):
    container, seed, run_id, _, writer = writer_workspace
    parent_id, task_id = seed.conversations[0], uuid4()
    subscriber = container.events.subscribe(seed.project)
    with container.database.transaction() as session:
        child_id = writer.create_child(
            session, NewChildConversation(seed.project, parent_id, task_id, "세부 조사", seed.owner)
        )
        # The writer flushes the conversation before task insertion. Its deferred FK is essential.
        assert session.get(TaskRow, task_id) is None
        session.add(TaskRow(
            id=task_id, source_conversation_id=parent_id, child_conversation_id=child_id,
            source_run_id=run_id, ordinal=2, title="세부 조사", goal="범위 확인", status="pending",
            requested_by=seed.owner,
        ))
        session.flush()
        session.execute(text("SET CONSTRAINTS fk_conversation_task_id_task IMMEDIATE"))
        assert await container.event_relay.flush() == 0
    with container.database.transaction() as session:
        child = session.get(ConversationRow, child_id)
        task = session.get(TaskRow, task_id)
        assert child.parent_id == task.source_conversation_id == parent_id
        assert child.task_id == task.id
        assert child.id == task.child_conversation_id
        assert child.origin == "branch"
    assert await container.event_relay.flush() == 1
    event = await subscriber.next(timeout=0.1)
    assert event.name == EventName.CONVERSATION_CREATED
    assert event.project_id == seed.project
    payload = event.data["conversation"]
    assert payload["id"] == child_id
    assert payload["project_id"] == seed.project
    assert payload["parent_id"] == parent_id
    assert payload["task_id"] == task_id
    assert payload["path"] == ("대화",)
    assert payload["created_by"] == seed.owner
    assert await subscriber.next(timeout=0.01) is None
    subscriber.close()


async def test_missing_deferred_task_rolls_back_child_and_event(writer_workspace):
    container, seed, _, _, writer = writer_workspace
    subscriber = container.events.subscribe(seed.project)
    with pytest.raises(IntegrityError, match="fk_conversation_task_id_task"):
        with container.database.transaction() as session:
            child_id = writer.create_child(
                session,
                NewChildConversation(seed.project, seed.conversations[0], uuid4(), "실패할 자식", seed.owner),
            )
    with container.database.transaction() as session:
        assert session.get(ConversationRow, child_id) is None
    assert await container.event_relay.flush() == 0
    assert await subscriber.next(timeout=0.01) is None
    subscriber.close()


def test_writer_lock_prevents_higher_cursor_from_passing_uncommitted_lower_message(writer_workspace):
    container, seed, run_id, repository, writer = writer_workspace
    first_written, release_first = Event(), Event()
    first_pid, second_pid = Queue(), Queue()
    conversation_id = seed.conversations[0]

    def first_write():
        with container.database.transaction() as session:
            first_pid.put(session.scalar(text("SELECT pg_backend_pid()")))
            identifier = writer.append_message(
                session, NewMessage(conversation_id, AuthorKind.AI, "먼저 저장", seed.owner, run_id)
            )
            first_written.set()
            assert release_first.wait(timeout=10), "The test did not release the first transaction"
        return identifier

    def second_write():
        with container.database.transaction() as session:
            second_pid.put(session.scalar(text("SELECT pg_backend_pid()")))
            return writer.append_message(
                session, NewMessage(conversation_id, AuthorKind.SYSTEM, "나중에 저장", seed.owner, run_id)
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(first_write)
        try:
            assert first_written.wait(timeout=5)
            blocker = first_pid.get(timeout=1)
            second = executor.submit(second_write)
            waiter = second_pid.get(timeout=5)
            deadline = time.monotonic() + 5
            while True:
                with container.database.transaction() as session:
                    blockers = session.scalar(text("SELECT pg_blocking_pids(:pid)"), {"pid": waiter})
                if blocker in blockers:
                    break
                assert time.monotonic() < deadline, "The second writer never waited for the first writer"
                time.sleep(0.01)
            # With the lower sequence uncommitted, the later writer cannot allocate/commit a higher
            # sequence. A reconnecting reader therefore cannot advance its cursor past the first.
            assert not second.done()
            with container.database.transaction() as session:
                assert repository.list_messages(session, conversation_id, after_seq=0, limit=200) == ()
                assert session.scalar(select(func.count()).select_from(MessageRow).where(
                    MessageRow.conversation_id == conversation_id,
                )) == 0
        finally:
            release_first.set()
        first_id, second_id = first.result(timeout=5), second.result(timeout=5)
    with container.database.transaction() as session:
        page = repository.list_messages(session, conversation_id, after_seq=0, limit=1)
        assert len(page) == 1
        assert page[0].id == first_id
        next_page = repository.list_messages(session, conversation_id, after_seq=page[0].seq, limit=200)
        assert [message.id for message in next_page] == [second_id]
        assert page[0].seq < next_page[0].seq
