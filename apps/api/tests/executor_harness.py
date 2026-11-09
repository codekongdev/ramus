"""Shared setup for executor integration tests: rows, runtimes, a manual clock, and gated models."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import insert, select, text, update

from ramus_api.modules.execution.application.config import ExecutorConfig
from ramus_api.modules.execution.composition import ExecutionRuntime, build_execution_runtime
from ramus_api.modules.execution.domain.models import LlmRequest, RunPurpose, RunRequest
from ramus_api.modules.execution.fakes.connections import FakeAiConnectionQuery
from ramus_api.modules.execution.fakes.context import FakeContextProvider
from ramus_api.modules.execution.fakes.handlers import FakeRunPurposeHandler
from ramus_api.modules.execution.fakes.llm import FakeLLM
from ramus_api.modules.execution.infrastructure.models import RunRow
from ramus_api.modules.realtime.domain.events import ProjectEvent
from ramus_api.modules.realtime.fakes.publisher import FakeEventPublisher
from ramus_api.orm_registry import metadata
from ramus_api.shared.infrastructure.database import Database

FAST = ExecutorConfig(
    poll_interval=timedelta(milliseconds=50),
    heartbeat_interval=timedelta(milliseconds=50),
    stale_after=timedelta(seconds=60),
    max_pending_wait=timedelta(minutes=10),
    llm_timeout=timedelta(seconds=10),
    maintenance_interval=timedelta(seconds=30),
    concurrency=2,
)


class ManualClock:
    def __init__(self) -> None:
        self.now = datetime.now(UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now = self.now + delta


@dataclass(frozen=True)
class Seed:
    owner: UUID
    other: UUID
    project: UUID
    conversations: tuple[UUID, ...]
    child: UUID
    result: UUID


def seed_rows(database: Database, conversations: int = 4) -> Seed:
    tables = metadata.tables
    owner, other, project, child, root_run, task, result = (uuid4() for _ in range(7))
    conversation_ids = tuple(uuid4() for _ in range(conversations))
    with database.transaction() as session:
        for account in (owner, other):
            session.execute(
                insert(tables["account"]).values(
                    id=account, email=f"{account}@example.test", display_name="테스트 참여자"
                )
            )
        session.execute(insert(tables["project"]).values(id=project, name="실행기 테스트"))
        for conversation in (*conversation_ids, child):
            session.execute(
                insert(tables["conversation"]).values(
                    id=conversation, project_id=project, title="대화", origin="top", created_by=owner
                )
            )
        session.execute(
            insert(tables["run"]).values(
                id=root_run,
                project_id=project,
                conversation_id=conversation_ids[0],
                purpose="work",
                status="succeeded",
                requested_by=owner,
                credential_account_id=owner,
                input_snapshot={},
            )
        )
        session.execute(
            insert(tables["task"]).values(
                id=task,
                source_conversation_id=conversation_ids[0],
                child_conversation_id=child,
                source_run_id=root_run,
                ordinal=1,
                title="작업",
                goal="목표",
                status="ready",
                requested_by=owner,
            )
        )
        session.execute(
            insert(tables["result"]).values(
                id=result, project_id=project, source_conversation_id=child, source_task_id=task, title="결과"
            )
        )
    return Seed(owner, other, project, conversation_ids, child, result)


def work_request(seed: Seed, conversation: UUID, requested_by: UUID | None = None) -> RunRequest:
    return RunRequest(seed.project, conversation, None, RunPurpose.WORK, None, requested_by or seed.owner)


def summary_request(seed: Seed, conversation: UUID, requested_by: UUID | None = None) -> RunRequest:
    return RunRequest(
        seed.project, conversation, None, RunPurpose.SUMMARY, seed.result, requested_by or seed.owner
    )


@dataclass
class Rig:
    runtime: ExecutionRuntime
    publisher: FakeEventPublisher
    connections: FakeAiConnectionQuery
    contexts: FakeContextProvider
    handler: FakeRunPurposeHandler
    clock: ManualClock


def build_rig(
    database: Database,
    seed: Seed,
    *,
    gateway: Any = None,
    handlers: Sequence[FakeRunPurposeHandler] | None = None,
    publisher: FakeEventPublisher | None = None,
    contexts: FakeContextProvider | None = None,
    clock: ManualClock | None = None,
    config: ExecutorConfig = FAST,
) -> Rig:
    handler_list = list(handlers) if handlers is not None else [FakeRunPurposeHandler()]
    rig_publisher = publisher or FakeEventPublisher()
    connections = FakeAiConnectionQuery({seed.owner, seed.other})
    rig_contexts = contexts or FakeContextProvider()
    rig_clock = clock or ManualClock()
    runtime = build_execution_runtime(
        transaction=database.transaction,
        publisher=rig_publisher,
        gateway=gateway or FakeLLM(),
        context_provider=rig_contexts,
        connections=connections,
        handlers=handler_list,
        config=config,
        clock=rig_clock,
    )
    return Rig(runtime, rig_publisher, connections, rig_contexts, handler_list[0], rig_clock)


def register(database: Database, rig: Rig, request: RunRequest) -> UUID:
    with database.transaction() as session:
        return rig.runtime.requester.request(session, request).run_id


def run_row(database: Database, run_id: UUID) -> Mapping[str, Any]:
    with database.transaction() as session:
        return session.execute(select(RunRow.__table__).where(RunRow.id == run_id)).mappings().one()


def set_run(database: Database, run_id: UUID, **values: Any) -> None:
    with database.transaction() as session:
        session.execute(update(RunRow.__table__).where(RunRow.id == run_id).values(**values))


def statuses(events: Sequence[ProjectEvent], run_id: UUID) -> list[str]:
    return [event.data["run"]["status"] for event in events if event.data["run"]["id"] == run_id]


def wait_for_lock_waiter(database: Database, timeout: float = 5.0) -> None:
    """Polls until another backend of this test database is blocked on a lock."""
    deadline = time.monotonic() + timeout
    query = text(
        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND wait_event_type = 'Lock'"
    )
    while time.monotonic() < deadline:
        with database.engine.connect() as connection:
            if connection.execute(query).scalar_one() > 0:
                return
        time.sleep(0.01)
    raise AssertionError("No backend started waiting on a lock")


async def drain(rig: Rig) -> int:
    count = 0
    while await rig.runtime.worker.run_once():
        count += 1
    return count


async def eventually(predicate: Any, timeout: float = 5.0) -> None:
    async with asyncio.timeout(timeout):
        while not await asyncio.to_thread(predicate):
            await asyncio.sleep(0.01)


class GatedLLM:
    """Holds every model call until ``release`` is set; records requests as the model saw them."""

    def __init__(self, inner: FakeLLM | None = None) -> None:
        self._inner = inner or FakeLLM()
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls: list[LlmRequest] = []

    async def complete(self, request: LlmRequest) -> Mapping[str, Any]:
        self.calls.append(request)
        self.started.set()
        await self.release.wait()
        return await self._inner.complete(request)


class ScriptedLLM:
    """Uses the n-th fake for the n-th call, then keeps the last one."""

    def __init__(self, *fakes: FakeLLM) -> None:
        self._fakes = fakes
        self.calls: list[LlmRequest] = []

    async def complete(self, request: LlmRequest) -> Mapping[str, Any]:
        fake = self._fakes[min(len(self.calls), len(self._fakes) - 1)]
        self.calls.append(request)
        return await fake.complete(request)
