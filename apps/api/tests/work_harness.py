"""SQL-only stand-ins for the unmerged A2 writer and B3 provider, using disposable test databases."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from executor_harness import FAST
from sqlalchemy import insert, literal, select, update
from sqlalchemy.orm import Session

from ramus_api.modules.conversations.domain.models import NewChildConversation, NewMessage
from ramus_api.modules.execution.composition import ExecutionRuntime
from ramus_api.modules.execution.domain.models import (
    ConversationContext,
    ResourceInput,
    RunPurpose,
    RunRequest,
)
from ramus_api.modules.execution.fakes.connections import FakeAiConnectionQuery
from ramus_api.modules.execution.fakes.llm import FakeLLM
from ramus_api.modules.execution.infrastructure.commit_hooks import SqlAlchemyTransactionHooks
from ramus_api.modules.execution.work_composition import build_work_execution_runtime
from ramus_api.modules.realtime.domain.events import EventName, ProjectEvent
from ramus_api.modules.realtime.fakes.publisher import FakeEventPublisher
from ramus_api.orm_registry import metadata
from ramus_api.shared.domain.primitives import utc_now
from ramus_api.shared.infrastructure.database import Database

BRANCH_JSON = json.dumps(
    {
        "mode": "branch",
        "reply": "가입·혜택·해지를 나눠 진행합니다.",
        "tasks": [
            {"title": name, "goal": f"{name} 정책 비교", "start_input": f"{name} 정책을 조사해줘"}
            for name in ("가입", "혜택", "해지")
        ],
    },
    ensure_ascii=False,
)


@dataclass(frozen=True)
class WorkSeed:
    owner: UUID
    other: UUID
    project: UUID
    parent: UUID


def seed_work(database: Database) -> WorkSeed:
    owner, other, project, parent = (uuid4() for _ in range(4))
    tables = metadata.tables
    with database.transaction() as session:
        # Every worker claims the database-wide queue; close leftovers from preceding tests.
        session.execute(
            update(tables["run"]).where(tables["run"].c.status.in_(("pending", "running"))).values(status="cancelled")
        )
        for account in (owner, other):
            session.execute(
                insert(tables["account"]).values(id=account, email=f"{account}@example.test", display_name="참여자")
            )
        session.execute(insert(tables["project"]).values(id=project, name="자동 분기 검증"))
        session.execute(
            insert(tables["conversation"]).values(
                id=parent, project_id=project, title="멤버십", origin="top", created_by=owner
            )
        )
    return WorkSeed(owner, other, project, parent)


class SqlTestWriter:
    """Uses the A2 contract, including deferred task FK and post-commit notifications."""

    def __init__(self) -> None:
        self.relay: Any = None
        self._hooks = SqlAlchemyTransactionHooks()

    def _event(self, session: Session, event: ProjectEvent) -> None:
        self._hooks.after_commit(session, lambda: self.relay.enqueue(event))

    def after_commit(self, session: Session, event: ProjectEvent) -> None:
        """Also serves as the committed-event boundary for the genuine A2 SQL writer."""
        self._event(session, event)

    def append_message(self, session: Session, message: NewMessage) -> UUID:
        return self.append(
            session, message.conversation_id, message.body, message.author_kind.value,
            requested_by=message.requested_by, run_id=message.run_id,
        )[0]

    def append(
        self, session: Session, conversation_id: UUID, body: str, author_kind: str = "human", **values: Any
    ) -> tuple[UUID, int]:
        conversation, message = metadata.tables["conversation"], metadata.tables["message"]
        project_id = session.execute(
            select(conversation.c.project_id).where(conversation.c.id == conversation_id).with_for_update()
        ).scalar_one()
        row = session.execute(
            insert(message).values(
                id=uuid4(), conversation_id=conversation_id, body=body, author_kind=author_kind, **values
            ).returning(message.c.id, message.c.seq)
        ).one()
        self._event(
            session,
            ProjectEvent(
                project_id, EventName.MESSAGE_CREATED, utc_now(),
                {"conversation_id": conversation_id, "message_id": row.id, "seq": row.seq},
            ),
        )
        return row.id, row.seq

    def create_child(self, session: Session, conversation: NewChildConversation) -> UUID:
        table = metadata.tables["conversation"]
        identifier = uuid4()
        row = session.execute(
            insert(table).values(
                id=identifier, project_id=conversation.project_id, parent_id=conversation.parent_id,
                task_id=conversation.task_id, title=conversation.title, origin="branch", created_by=conversation.created_by,
            ).returning(table)
        ).mappings().one()
        parent_title = session.execute(select(table.c.title).where(table.c.id == conversation.parent_id)).scalar_one()
        payload = {key: row[key] for key in ("id", "project_id", "parent_id", "task_id", "title", "created_by", "created_at")}
        payload["path"] = [parent_title]
        self._event(
            session,
            ProjectEvent(
                conversation.project_id, EventName.CONVERSATION_CREATED, utc_now(),
                {"project_id": conversation.project_id, "conversation": payload},
            ),
        )
        return identifier


class SqlTestContexts:
    """Reads/copies actual revision pins, with an injected failure after a configured copy."""

    def __init__(self) -> None:
        self.copies = 0
        self.fail_copy: int | None = None
        self.after_copy: Callable[[int], None] | None = None

    def snapshot(self, session: Session, conversation_id: UUID) -> ConversationContext:
        tables = metadata.tables
        pin, revision, resource = (tables[key] for key in ("conversation_resource", "resource_revision", "resource"))
        rows = session.execute(
            select(pin.c.resource_id, pin.c.revision_id, resource.c.kind, revision.c.name, revision.c.instructions, revision.c.content)
            .select_from(pin.join(revision, revision.c.id == pin.c.revision_id).join(resource, resource.c.id == pin.c.resource_id))
            .where(pin.c.conversation_id == conversation_id).order_by(pin.c.resource_id)
        ).all()
        return ConversationContext(tuple(ResourceInput(*row) for row in rows))

    def copy_resources(self, session: Session, source_conversation_id: UUID, target_conversation_id: UUID) -> None:
        pin = metadata.tables["conversation_resource"]
        session.execute(
            insert(pin).from_select(
                ["conversation_id", "resource_id", "revision_id", "applied_by"],
                select(literal(target_conversation_id), pin.c.resource_id, pin.c.revision_id, pin.c.applied_by)
                .where(pin.c.conversation_id == source_conversation_id),
            )
        )
        self.copies += 1
        if self.after_copy is not None:
            self.after_copy(self.copies)
        if self.copies == self.fail_copy:
            raise RuntimeError("Injected resource copy failure")


@dataclass
class WorkRig:
    runtime: ExecutionRuntime
    gateway: Any
    publisher: FakeEventPublisher
    writer: SqlTestWriter
    contexts: SqlTestContexts


def work_rig(database: Database, seed: WorkSeed, gateway: Any = None) -> WorkRig:
    writer, contexts, publisher = SqlTestWriter(), SqlTestContexts(), FakeEventPublisher()
    gateway = gateway or FakeLLM(work_json=BRANCH_JSON)
    runtime = build_work_execution_runtime(
        transaction=database.transaction, publisher=publisher, gateway=gateway, context_provider=contexts,
        connections=FakeAiConnectionQuery({seed.owner, seed.other}), writer=writer, config=FAST,
    )
    writer.relay = runtime.relay
    return WorkRig(runtime, gateway, publisher, writer, contexts)


def request_work(
    database: Database, rig: WorkRig, seed: WorkSeed, *, conversation_id: UUID | None = None,
    task_id: UUID | None = None, body: str = "@AI 가입·혜택·해지로 벤치마킹을 나눠 진행해줘", account_id: UUID | None = None,
) -> tuple[UUID, int]:
    conversation_id, account_id = conversation_id or seed.parent, account_id or seed.owner
    with database.transaction() as session:
        run = rig.runtime.requester.request(
            session, RunRequest(seed.project, conversation_id, task_id, RunPurpose.WORK, None, account_id)
        )
        _, seq = rig.writer.append(
            session, conversation_id, body, author_account_id=account_id, requested_by=account_id, run_id=run.run_id
        )
    return run.run_id, seq


def rows(database: Database, name: str, **conditions: Any) -> list[dict[str, Any]]:
    table = metadata.tables[name]
    with database.transaction() as session:
        statement = select(table).where(*(table.c[key] == value for key, value in conditions.items()))
        return [dict(row) for row in session.execute(statement).mappings()]


def add_resource(database: Database, seed: WorkSeed) -> tuple[UUID, UUID, UUID]:
    """Parent explicitly pins v1 while the resource's latest head already points to v2."""
    resource_id, v1, v2 = (uuid4() for _ in range(3))
    tables = metadata.tables
    with database.transaction() as session:
        session.execute(
            insert(tables["resource"]).values(
                id=resource_id, project_id=seed.project, kind="skill", latest_revision_id=v2, created_by=seed.owner
            )
        )
        for number, identifier, base in ((1, v1, None), (2, v2, v1)):
            session.execute(
                insert(tables["resource_revision"]).values(
                    id=identifier, resource_id=resource_id, number=number, name=f"조사 기준 v{number}",
                    description="검증 자료", instructions=f"v{number} 지침", content_hash=str(number) * 64,
                    base_revision_id=base, created_by=seed.owner,
                )
            )
        session.execute(
            insert(tables["conversation_resource"]).values(
                conversation_id=seed.parent, resource_id=resource_id, revision_id=v1, applied_by=seed.owner
            )
        )
    return resource_id, v1, v2
