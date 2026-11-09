"""Execution-owned historical examples and offline maintenance operations."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from ramus_api.modules.execution.infrastructure.models import RunRow, TaskRow


class SampleExecution:
    def run(
        self, session: Session, *, identifier: UUID, project_id: UUID, conversation_id: UUID,
        author_id: UUID, at: datetime, snapshot: dict, task_id: UUID | None = None,
    ) -> None:
        session.add(RunRow(
            id=identifier, project_id=project_id, conversation_id=conversation_id,
            task_id=task_id, purpose="work", status="succeeded", requested_by=author_id,
            credential_account_id=author_id, input_snapshot=snapshot, created_at=at,
            started_at=at, finished_at=at,
        ))
        session.flush()

    def task(
        self, session: Session, *, identifier: UUID, source_id: UUID, child_id: UUID,
        source_run_id: UUID, ordinal: int, title: str, goal: str, author_id: UUID, at: datetime,
    ) -> None:
        session.add(TaskRow(
            id=identifier, source_conversation_id=source_id, child_conversation_id=child_id,
            source_run_id=source_run_id, ordinal=ordinal, title=title, goal=goal, status="ready",
            requested_by=author_id, created_at=at, started_at=at, finished_at=at,
        ))
        session.flush()

    def set_current_run(self, session: Session, task_id: UUID, run_id: UUID) -> None:
        session.execute(update(TaskRow).where(TaskRow.id == task_id).values(current_run_id=run_id))

    def require_idle(self, session: Session, project_ids: tuple[UUID, ...]) -> None:
        active = session.scalar(select(RunRow.id).where(
            RunRow.project_id.in_(project_ids), RunRow.status.in_(("pending", "running")),
        ).limit(1))
        if active is not None:
            raise RuntimeError("Sample reset refused: pending or running executions exist")

    def ids(self, session: Session, project_ids: tuple[UUID, ...]) -> tuple[UUID, ...]:
        return tuple(session.scalars(select(RunRow.id).where(RunRow.project_id.in_(project_ids))))

    def task_ids(self, session: Session, conversation_ids: tuple[UUID, ...]) -> tuple[UUID, ...]:
        return tuple(session.scalars(select(TaskRow.id).where(TaskRow.child_conversation_id.in_(conversation_ids))))

    def detach(self, session: Session, run_ids: tuple[UUID, ...], conversation_ids: tuple[UUID, ...]) -> None:
        # Summary targets are mandatory for purpose=summary; switch only rows about to be deleted.
        session.execute(update(RunRow).where(RunRow.id.in_(run_ids)).values(task_id=None, target_id=None, purpose="work"))
        session.execute(update(TaskRow).where(TaskRow.child_conversation_id.in_(conversation_ids)).values(current_run_id=None))

    def clear(self, session: Session, run_ids: tuple[UUID, ...], conversation_ids: tuple[UUID, ...]) -> None:
        session.execute(delete(TaskRow).where(TaskRow.child_conversation_id.in_(conversation_ids)))
        session.execute(delete(RunRow).where(RunRow.id.in_(run_ids)))
