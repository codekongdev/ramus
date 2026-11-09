"""SQLAlchemy implementation of ``ResourceRepository``. Revisions are only ever inserted."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, func, insert, or_, select
from sqlalchemy.orm import Session

from ramus_api.modules.resources.application.ports import (
    AppliedRecord,
    NewResource,
    ResourceHistory,
    ResourceRecord,
    RevisionEntry,
    RevisionRecord,
)
from ramus_api.modules.resources.domain.models import ResourceKind
from ramus_api.modules.resources.domain.rules import RevisionContent, RevisionRef
from ramus_api.modules.resources.infrastructure.models import (
    ConversationResourceRow,
    ResourceRevisionRow,
    ResourceRow,
)

FIRST_REVISION_NUMBER = 1


def _like_pattern(query: str) -> str:
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _revision(row: ResourceRevisionRow) -> RevisionRecord:
    return RevisionRecord(
        id=row.id,
        resource_id=row.resource_id,
        number=row.number,
        content=RevisionContent(row.name, row.description, row.instructions, row.content, row.file_name),
        created_by=row.created_by,
        created_at=row.created_at,
    )


def _resource(resource: ResourceRow, latest: ResourceRevisionRow) -> ResourceRecord:
    return ResourceRecord(resource.id, resource.project_id, ResourceKind(resource.kind), _revision(latest))


class SqlResourceRepository:
    def add(self, session: Session, resource: NewResource) -> None:
        # resource.latest_revision_id -> resource_revision is DEFERRABLE INITIALLY DEFERRED,
        # so the head row can go first inside the same transaction.
        session.execute(
            insert(ResourceRow).values(
                id=resource.resource_id,
                project_id=resource.project_id,
                kind=resource.kind.value,
                latest_revision_id=resource.revision_id,
                created_by=resource.created_by,
            )
        )
        content = resource.content
        session.execute(
            insert(ResourceRevisionRow).values(
                id=resource.revision_id,
                resource_id=resource.resource_id,
                number=FIRST_REVISION_NUMBER,
                name=content.name,
                description=content.description,
                instructions=content.instructions,
                content=content.content,
                file_name=content.file_name,
                content_hash=resource.content_hash,
                base_revision_id=None,
                created_by=resource.created_by,
            )
        )

    def history(self, session: Session, resource_id: UUID) -> ResourceHistory | None:
        head = session.execute(
            select(ResourceRow, ResourceRevisionRow)
            .join(ResourceRevisionRow, ResourceRevisionRow.id == ResourceRow.latest_revision_id)
            .where(ResourceRow.id == resource_id)
        ).one_or_none()
        if head is None:
            return None
        entries = session.execute(
            select(
                ResourceRevisionRow.id,
                ResourceRevisionRow.number,
                ResourceRevisionRow.name,
                ResourceRevisionRow.created_by,
                ResourceRevisionRow.created_at,
            )
            .where(ResourceRevisionRow.resource_id == resource_id)
            .order_by(ResourceRevisionRow.number)
        ).all()
        return ResourceHistory(_resource(*head), tuple(RevisionEntry(*entry) for entry in entries))

    def search(self, session: Session, project_id: UUID, query: str) -> Sequence[ResourceRecord]:
        statement = (
            select(ResourceRow, ResourceRevisionRow)
            .join(ResourceRevisionRow, ResourceRevisionRow.id == ResourceRow.latest_revision_id)
            .where(ResourceRow.project_id == project_id)
            .order_by(func.lower(ResourceRevisionRow.name), ResourceRow.created_at, ResourceRow.id)
        )
        if query:
            pattern = _like_pattern(query)
            statement = statement.where(
                or_(
                    ResourceRevisionRow.name.ilike(pattern, escape="\\"),
                    ResourceRevisionRow.description.ilike(pattern, escape="\\"),
                )
            )
        return [_resource(resource, latest) for resource, latest in session.execute(statement).all()]

    def applied(self, session: Session, conversation_id: UUID) -> Sequence[AppliedRecord]:
        rows = session.execute(
            select(
                ConversationResourceRow.resource_id,
                ConversationResourceRow.revision_id,
                ResourceRevisionRow.number,
                ResourceRevisionRow.name,
                ResourceRow.kind,
            )
            .join(ResourceRevisionRow, ResourceRevisionRow.id == ConversationResourceRow.revision_id)
            .join(ResourceRow, ResourceRow.id == ConversationResourceRow.resource_id)
            .where(ConversationResourceRow.conversation_id == conversation_id)
            .order_by(func.lower(ResourceRevisionRow.name), ConversationResourceRow.resource_id)
        ).all()
        return [
            AppliedRecord(r.resource_id, r.revision_id, r.number, r.name, ResourceKind(r.kind)) for r in rows
        ]

    def revision_refs(self, session: Session, revision_ids: Sequence[UUID]) -> Sequence[RevisionRef]:
        if not revision_ids:
            return []
        rows = session.execute(
            select(ResourceRevisionRow.id, ResourceRevisionRow.resource_id, ResourceRow.project_id)
            .join(ResourceRow, ResourceRow.id == ResourceRevisionRow.resource_id)
            .where(ResourceRevisionRow.id.in_(revision_ids))
        ).all()
        return [RevisionRef(r.id, r.resource_id, r.project_id) for r in rows]

    def replace_applied(
        self, session: Session, conversation_id: UUID, revisions: Sequence[RevisionRef], applied_by: UUID
    ) -> None:
        session.execute(
            delete(ConversationResourceRow).where(ConversationResourceRow.conversation_id == conversation_id)
        )
        if revisions:
            session.execute(
                insert(ConversationResourceRow),
                [
                    {
                        "conversation_id": conversation_id,
                        "resource_id": ref.resource_id,
                        "revision_id": ref.revision_id,
                        "applied_by": applied_by,
                    }
                    for ref in revisions
                ],
            )
