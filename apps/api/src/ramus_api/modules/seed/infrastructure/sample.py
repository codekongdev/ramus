"""Compose module-owned sample interfaces for explicit, transactional CLI preparation."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from ramus_api.modules.access.public import ensure_example_author, grant_sample_followup_memberships
from ramus_api.modules.conversations.public import SampleConversations
from ramus_api.modules.execution.public import SampleExecution
from ramus_api.modules.projects.public import (
    FOLLOWUP_SAMPLE_PROJECT_ID,
    SHARED_SAMPLE_PROJECT_ID,
    ensure_followup_sample_project,
    ensure_shared_sample_project,
    lock_sample_preparation,
)
from ramus_api.modules.resources.public import SampleResources
from ramus_api.modules.results.public import SampleResults
from ramus_api.modules.seed.application.setup import PrepareSample
from ramus_api.modules.seed.domain.content import (
    AUTHORS,
    DESIGN_MESSAGES,
    DESIGN_TITLE,
    RESEARCH,
    RESOURCES,
    sample_id,
)
from ramus_api.modules.seed.infrastructure.models import SeedMarkerRow
from ramus_api.modules.sharing.public import SampleSharing
from ramus_api.shared.infrastructure.database import Database
from ramus_api.shared.infrastructure.receipts import forget_entity_receipts

SHARED_SAMPLE_MARKER_KEY = "ramus:shared-sample:membership:project"
SHARED_SAMPLE_VERSION = 1
CONTENT_MARKER_KEY = "ramus:shared-sample:membership:content"
SAMPLE_PROJECT_IDS = (SHARED_SAMPLE_PROJECT_ID, FOLLOWUP_SAMPLE_PROJECT_ID)
EXAMPLE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


class SqlSampleStore:
    conversations = SampleConversations()
    execution = SampleExecution()
    resources = SampleResources()
    results = SampleResults()
    sharing = SampleSharing()

    def lock(self, session: Session, *, resetting: bool) -> None:
        lock_sample_preparation(session, exclusive=True)
        if resetting:
            # Offline maintenance: fail if an API transaction is still using the space.
            # Writes are locked before checking active runs, closing the registration race.
            session.execute(text(
                "LOCK TABLE account, project, membership, conversation, message, task, run, "
                "resource, resource_revision, conversation_resource, result, result_draft, "
                "result_revision, share, conversation_input, seed_marker, request_receipt "
                "IN EXCLUSIVE MODE NOWAIT"
            ))

    def ensure_base(self, session: Session) -> UUID:
        project_id = ensure_shared_sample_project(session)
        session.execute(insert(SeedMarkerRow).values(
            key=SHARED_SAMPLE_MARKER_KEY, version=SHARED_SAMPLE_VERSION,
        ).on_conflict_do_nothing(index_elements=[SeedMarkerRow.key]))
        marker = session.get(SeedMarkerRow, SHARED_SAMPLE_MARKER_KEY)
        if marker is None or marker.version != SHARED_SAMPLE_VERSION:
            raise RuntimeError("The shared sample seed version requires an explicit migration")
        return project_id

    def content_version(self, session: Session) -> int | None:
        marker = session.get(SeedMarkerRow, CONTENT_MARKER_KEY)
        return marker.version if marker else None

    def mark_content(self, session: Session, version: int) -> None:
        session.execute(insert(SeedMarkerRow).values(key=CONTENT_MARKER_KEY, version=version))

    def grant_participants(self, session: Session) -> None:
        followup_id = ensure_followup_sample_project(session)
        grant_sample_followup_memberships(session, SHARED_SAMPLE_PROJECT_ID, followup_id)

    def install(self, session: Session) -> None:
        for author in AUTHORS:
            ensure_example_author(session, sample_id(f"author:{author.key}"), author.key, author.label)
        ensure_followup_sample_project(session)
        leader_id = sample_id("author:leader")
        design_id = sample_id("conversation:design")
        self.conversations.add(
            session, identifier=design_id, project_id=SHARED_SAMPLE_PROJECT_ID, title=DESIGN_TITLE,
            author_id=leader_id, seed_key="ramus:shared-sample:membership:conversation:design",
            created_at=EXAMPLE_TIME,
        )
        design_range = self._messages(session, "design", design_id, DESIGN_MESSAGES)
        revision_ids = [sample_id(f"resource:{item.key}:v1") for item in RESOURCES]
        for item, revision_id in zip(RESOURCES, revision_ids, strict=True):
            self.resources.add(
                session, identifier=sample_id(f"resource:{item.key}"), revision_id=revision_id,
                project_id=SHARED_SAMPLE_PROJECT_ID, author_id=leader_id,
                seed_key=f"ramus:shared-sample:membership:resource:{item.key}", kind=item.kind,
                name=item.name, description=item.description, body=item.body,
            )
        source_run_id = sample_id("run:example-research")
        self.execution.run(
            session, identifier=source_run_id, project_id=SHARED_SAMPLE_PROJECT_ID,
            conversation_id=design_id, author_id=leader_id, at=EXAMPLE_TIME,
            snapshot={"message_from_seq": design_range[0], "message_to_seq": design_range[1],
                      "resource_revision_ids": [str(i) for i in revision_ids], "input_result_revision_ids": []},
        )
        for ordinal, item in enumerate(RESEARCH, start=1):
            conversation_id = sample_id(f"conversation:{item.key}")
            task_id, run_id = sample_id(f"task:{item.key}"), sample_id(f"run:{item.key}")
            author_id = sample_id(f"author:{item.author_key}")
            self.conversations.add(
                session, identifier=conversation_id, project_id=SHARED_SAMPLE_PROJECT_ID,
                title=item.title, author_id=author_id,
                seed_key=f"ramus:shared-sample:membership:conversation:{item.key}",
                created_at=EXAMPLE_TIME + timedelta(minutes=ordinal), parent_id=design_id, task_id=task_id,
            )
            message_from, message_to = self._messages(session, item.key, conversation_id, item.messages)
            self.execution.task(
                session, identifier=task_id, source_id=design_id, child_id=conversation_id,
                source_run_id=source_run_id, ordinal=ordinal, title=item.title,
                goal=f"가상 예시 조사: {item.title}", author_id=author_id, at=EXAMPLE_TIME,
            )
            snapshot = {"message_from_seq": message_from, "message_to_seq": message_to,
                        "resource_revision_ids": [str(i) for i in revision_ids], "input_result_revision_ids": []}
            self.execution.run(
                session, identifier=run_id, project_id=SHARED_SAMPLE_PROJECT_ID,
                conversation_id=conversation_id, author_id=author_id, at=EXAMPLE_TIME,
                snapshot=snapshot, task_id=task_id,
            )
            self.execution.set_current_run(session, task_id, run_id)
            source = {"conversation_id": str(conversation_id), "run_id": str(run_id), **snapshot}
            result_id = sample_id(f"result:{item.key}")
            result_revision_id = sample_id(f"result:{item.key}:v1")
            title = f"{item.title} 결론 · {next(a.label for a in AUTHORS if a.key == item.author_key)}"
            self.results.add(
                session, identifier=result_id, revision_id=result_revision_id,
                project_id=SHARED_SAMPLE_PROJECT_ID, conversation_id=conversation_id, task_id=task_id,
                title=title, conclusion=item.conclusion, source=source, author_id=author_id,
            )
            self.sharing.add(
                session, identifier=sample_id(f"share:{item.key}:design"),
                input_id=sample_id(f"input:{item.key}:design"),
                conversation_id=design_id, result_id=result_id, revision_id=result_revision_id,
                title=title, conclusion=item.conclusion, source=source, author_id=author_id,
            )
        for key in ("design", *(item.key for item in RESEARCH)):
            for item, revision_id in zip(RESOURCES, revision_ids, strict=True):
                self.resources.pin(
                    session, conversation_id=sample_id(f"conversation:{key}"),
                    resource_id=sample_id(f"resource:{item.key}"), revision_id=revision_id, author_id=leader_id,
                )

    def _messages(self, session: Session, key: str, conversation_id: UUID, messages: tuple) -> tuple[int, int]:
        seqs = []
        for index, message in enumerate(messages):
            author = next(a for a in AUTHORS if a.key == message.author_key)
            seqs.append(self.conversations.message(
                session, identifier=sample_id(f"message:{key}:{index}"), conversation_id=conversation_id,
                author_id=sample_id(f"author:{author.key}"), author_label=author.label, body=message.body,
                created_at=EXAMPLE_TIME + timedelta(seconds=index),
            ))
        return seqs[0], seqs[-1]

    def require_idle(self, session: Session) -> None:
        self.execution.require_idle(session, SAMPLE_PROJECT_IDS)

    def clear(self, session: Session) -> None:
        conversation_ids = self.conversations.ids(session, SAMPLE_PROJECT_IDS)
        run_ids = self.execution.ids(session, SAMPLE_PROJECT_IDS)
        result_ids = self.results.ids(session, SAMPLE_PROJECT_IDS)
        revision_ids = self.results.revision_ids(session, SAMPLE_PROJECT_IDS)
        resource_ids = self.resources.entity_ids(session, SAMPLE_PROJECT_IDS)
        task_ids = self.execution.task_ids(session, conversation_ids)
        self.sharing.clear(session, conversation_ids, result_ids, revision_ids)
        self.resources.clear(session, SAMPLE_PROJECT_IDS, conversation_ids)
        self.conversations.clear_messages(session, conversation_ids)
        self.execution.detach(session, run_ids, conversation_ids)
        self.results.clear(session, SAMPLE_PROJECT_IDS)
        self.execution.clear(session, run_ids, conversation_ids)
        self.conversations.clear(session, conversation_ids)
        forget_entity_receipts(session, (
            *SAMPLE_PROJECT_IDS, *conversation_ids, *run_ids, *task_ids,
            *result_ids, *revision_ids, *resource_ids,
        ))
        session.execute(delete(SeedMarkerRow).where(SeedMarkerRow.key == CONTENT_MARKER_KEY))


def prepare_shared_sample(
    database: Database, *, reset_project_id: UUID | None = None, work_preserved: bool = False,
) -> UUID:
    try:
        return PrepareSample(database.transaction, SqlSampleStore())(
            reset_project_id=reset_project_id, work_preserved=work_preserved,
        )
    except IntegrityError:
        raise RuntimeError("Sample identity or external reference conflict; no changes were committed") from None
    except DBAPIError as error:
        if getattr(error.orig, "sqlstate", None) == "55P03":
            raise RuntimeError("Sample reset refused: database is in use; stop the API and workers first") from None
        raise
