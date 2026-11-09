"""Resource-owned seed revisions, with the same validation and hashes as authored resources."""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ramus_api.modules.resources.domain.models import ResourceKind
from ramus_api.modules.resources.domain.rules import content_hash, normalize_content
from ramus_api.modules.resources.infrastructure.models import (
    ConversationResourceRow,
    ResourceRevisionRow,
    ResourceRow,
)


class SampleResources:
    def add(
        self, session: Session, *, identifier: UUID, revision_id: UUID, project_id: UUID,
        author_id: UUID, seed_key: str, kind: str, name: str, description: str, body: str,
    ) -> None:
        content = normalize_content(
            ResourceKind(kind), name=name, description=description,
            instructions=body if kind == "skill" else None,
            content=body if kind != "skill" else None, file_name=None,
        )
        session.add(ResourceRow(
            id=identifier, project_id=project_id, kind=kind,
            latest_revision_id=revision_id, created_by=author_id, seed_key=seed_key,
        ))
        session.flush()
        session.add(ResourceRevisionRow(
            id=revision_id, resource_id=identifier, number=1, name=content.name,
            description=content.description, instructions=content.instructions,
            content=content.content, file_name=content.file_name, content_hash=content_hash(content),
            created_by=author_id,
        ))
        session.flush()

    def pin(
        self, session: Session, *, conversation_id: UUID, resource_id: UUID,
        revision_id: UUID, author_id: UUID,
    ) -> None:
        session.add(ConversationResourceRow(
            conversation_id=conversation_id, resource_id=resource_id,
            revision_id=revision_id, applied_by=author_id,
        ))
        session.flush()

    def clear(self, session: Session, project_ids: tuple[UUID, ...], conversation_ids: tuple[UUID, ...]) -> None:
        resource_ids = select(ResourceRow.id).where(ResourceRow.project_id.in_(project_ids))
        external = session.scalar(select(ConversationResourceRow.conversation_id).where(
            ConversationResourceRow.resource_id.in_(resource_ids),
            ConversationResourceRow.conversation_id.not_in(conversation_ids),
        ).limit(1))
        if external is not None:
            raise RuntimeError("Sample reset refused: another project references sample resources")
        session.execute(delete(ConversationResourceRow).where(ConversationResourceRow.conversation_id.in_(conversation_ids)))
        session.execute(delete(ResourceRevisionRow).where(ResourceRevisionRow.resource_id.in_(resource_ids)))
        session.execute(delete(ResourceRow).where(ResourceRow.project_id.in_(project_ids)))

    def entity_ids(self, session: Session, project_ids: tuple[UUID, ...]) -> tuple[UUID, ...]:
        resource_ids = tuple(session.scalars(select(ResourceRow.id).where(ResourceRow.project_id.in_(project_ids))))
        revision_ids = tuple(session.scalars(select(ResourceRevisionRow.id).where(ResourceRevisionRow.resource_id.in_(resource_ids))))
        return (*resource_ids, *revision_ids)
