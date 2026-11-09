"""Results-owned SQL persistence. A conditional head update and its immutable revision are atomic."""

from dataclasses import asdict
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from ramus_api.modules.execution.domain.models import ConversationContext, ResourceInput, ResultInput
from ramus_api.modules.results.domain.records import Draft, ResultRecord, Revision, Source
from ramus_api.modules.results.infrastructure.models import ResultDraftRow, ResultRevisionRow, ResultRow
from ramus_api.shared.domain.primitives import utc_now


def _json(value):
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(item) for item in value]
    return value


def _context(value) -> ConversationContext:
    return ConversationContext(
        tuple(ResourceInput(**{**item, "resource_id": UUID(item["resource_id"]),
                               "revision_id": UUID(item["revision_id"])}) for item in value.get("resources", [])),
        tuple(ResultInput(**{**item, "result_id": UUID(item["result_id"]),
                             "result_revision_id": UUID(item["result_revision_id"])}) for item in value.get("results", [])),
    )


def _revision(row: ResultRevisionRow) -> Revision:
    source = row.source
    return Revision(
        row.id, row.result_id, row.version, row.title, row.conclusion,
        Source(UUID(source["conversation_id"]), source["message_from_seq"], source["message_to_seq"],
               tuple(UUID(item) for item in source["resource_revision_ids"]),
               tuple(UUID(item) for item in source["input_result_revision_ids"]), UUID(source["run_id"])),
        row.saved_by, row.created_at,
    )


class SqlResultRepository:
    def get(self, session: Session, result_id: UUID, *, lock: bool = False) -> ResultRecord | None:
        query = select(ResultRow).where(ResultRow.id == result_id).execution_options(populate_existing=True)
        if lock:
            query = query.with_for_update()
        row = session.scalar(query)
        if row is None:
            return None
        draft_row = session.get(ResultDraftRow, result_id, populate_existing=True)
        draft = None if draft_row is None else Draft(
            draft_row.status, draft_row.conclusion, draft_row.base_version, draft_row.run_id,
            draft_row.message_from_seq, draft_row.message_to_seq, _context(draft_row.context_snapshot),
            draft_row.error_code, draft_row.updated_at,
        )
        revisions = tuple(_revision(revision) for revision in session.scalars(
            select(ResultRevisionRow).where(ResultRevisionRow.result_id == result_id)
            .order_by(ResultRevisionRow.version.desc())
        ))
        return ResultRecord(row.id, row.project_id, row.source_conversation_id, row.source_task_id, row.title,
                            row.latest_revision_id, row.latest_version, draft, revisions)

    def for_task(self, session: Session, task_id: UUID) -> ResultRecord | None:
        result_id = session.scalar(select(ResultRow.id).where(ResultRow.source_task_id == task_id))
        return None if result_id is None else self.get(session, result_id)

    def create(self, session, result_id, project_id, conversation_id, task_id, title) -> None:
        session.add(ResultRow(id=result_id, project_id=project_id, source_conversation_id=conversation_id,
                              source_task_id=task_id, title=title, latest_version=0))
        session.flush()

    def revision(self, session: Session, revision_id: UUID) -> Revision | None:
        row = session.get(ResultRevisionRow, revision_id)
        return None if row is None else _revision(row)

    def start_draft(self, session, result, run_id, bounds, context) -> None:
        row = session.get(ResultDraftRow, result.id)
        values = dict(status="generating", conclusion=None, base_version=result.latest_version, run_id=run_id,
                      message_from_seq=bounds[0], message_to_seq=bounds[1], error_code=None, error_params=None,
                      context_snapshot=_json(asdict(context)), updated_at=utc_now())
        if row is None:
            session.add(ResultDraftRow(result_id=result.id, **values))
        else:
            for key, value in values.items():
                setattr(row, key, value)
        session.flush()

    def finish_draft(self, session, result_id, run_id, conclusion, error_code) -> bool:
        changed = session.execute(
            update(ResultDraftRow).where(
                ResultDraftRow.result_id == result_id, ResultDraftRow.run_id == run_id,
                ResultDraftRow.status == "generating",
            ).values(status="failed" if error_code else "ready", conclusion=conclusion,
                     error_code=error_code, error_params=None, updated_at=utc_now())
            .returning(ResultDraftRow.result_id)
        ).one_or_none()
        return changed is not None

    def save(self, session, result, revision_id, base_version, conclusion, source, actor_id) -> Revision | None:
        next_version = base_version + 1
        changed = session.execute(
            update(ResultRow).where(ResultRow.id == result.id, ResultRow.latest_version == base_version)
            .values(latest_version=next_version, latest_revision_id=revision_id)
            .returning(ResultRow.id)
        ).one_or_none()
        if changed is None:
            return None
        row = ResultRevisionRow(id=revision_id, result_id=result.id, version=next_version,
                                title=result.title, conclusion=conclusion, source=_json(asdict(source)), saved_by=actor_id)
        session.add(row)
        session.flush()
        session.refresh(row)
        session.execute(delete(ResultDraftRow).where(
            ResultDraftRow.result_id == result.id, ResultDraftRow.run_id == source.run_id,
        ))
        return _revision(row)
