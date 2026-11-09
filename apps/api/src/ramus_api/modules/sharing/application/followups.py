"""Create a root conversation and its single approved conclusion in one transaction."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from ramus_api.modules.access.public import MembershipReader, TransactionFactory
from ramus_api.modules.conversations.application.ports import CommittedEvents
from ramus_api.modules.realtime.domain.events import EventName, ProjectEvent
from ramus_api.modules.results.public import ApprovedConclusion
from ramus_api.shared.application.idempotency import IdempotentExecutor
from ramus_api.shared.domain.errors import BusinessError
from ramus_api.shared.domain.primitives import utc_now
from ramus_api.shared.presentation.error_messages import message_for, register_error_messages
from ramus_api.shared.presentation.errors import INVALID_INPUT, INVALID_INPUT_MESSAGE, http_error_code

register_error_messages({
    "PROJECT_CREATE_FORBIDDEN": "이 프로젝트에 대화를 만들 권한이 없습니다. 다른 프로젝트를 선택해 주세요.",
})


@dataclass(frozen=True)
class PinnedConclusion:
    id: UUID
    conversation_id: UUID
    result_id: UUID
    result_revision_id: UUID
    version: int
    title: str
    conclusion: str
    source: dict[str, Any]
    origin: str
    created_by: UUID
    created_at: datetime


class Conversations(Protocol):
    def project_id(self, session: Any, conversation_id: UUID) -> UUID | None: ...
    def create_root(self, session: Any, project_id: UUID, title: str, actor_id: UUID) -> dict: ...


class ApprovedConclusions(Protocol):
    def get(self, session: Any, revision_id: UUID) -> ApprovedConclusion | None: ...


class Inputs(Protocol):
    def received(self, session: Any, revision_id: UUID) -> tuple[PinnedConclusion, ...]: ...
    def list(self, session: Any, conversation_id: UUID) -> tuple[PinnedConclusion, ...]: ...
    def add(self, session: Any, conversation_id: UUID, revision: ApprovedConclusion, actor_id: UUID) -> None: ...


def missing() -> BusinessError:
    code, message = http_error_code(404)
    return BusinessError(code, message, status=404)


def validate_title(title: str) -> None:
    try:
        if not title.strip() or len(title) > 100 or "\x00" in title:
            raise ValueError()
        title.encode("utf-8")
    except (ValueError, UnicodeEncodeError):
        raise BusinessError(INVALID_INPUT, INVALID_INPUT_MESSAGE, status=422) from None


@dataclass(frozen=True)
class FollowupService:
    transactions: TransactionFactory[Any]
    memberships: MembershipReader[Any]
    conversations: Conversations
    conclusions: ApprovedConclusions
    inputs: Inputs
    idempotency: IdempotentExecutor[Any]
    events: CommittedEvents[Any]

    def _revision(self, session, actor_id: UUID, revision_id: UUID) -> ApprovedConclusion:
        revision = self.conclusions.get(session, revision_id)
        if revision is None:
            raise missing()
        projects = set(self.memberships.project_ids(session, actor_id))
        if revision.project_id in projects:
            return revision
        # A recipient can reuse the exact version they received without gaining access to
        # source messages, resources, other revisions, or the source project's members.
        for received in self.inputs.received(session, revision_id):
            if self.conversations.project_id(session, received.conversation_id) in projects:
                return ApprovedConclusion(
                    received.result_revision_id, received.result_id, revision.project_id,
                    received.version, received.version, received.title, received.conclusion, received.source,
                )
        raise missing()

    def _authorize(self, session, project_id: UUID, actor_id: UUID, revision_id: UUID) -> ApprovedConclusion:
        if project_id not in self.memberships.project_ids(session, actor_id):
            raise BusinessError("PROJECT_CREATE_FORBIDDEN", message_for("PROJECT_CREATE_FORBIDDEN"), status=403)
        return self._revision(session, actor_id, revision_id)

    def create(self, project_id: UUID, actor_id: UUID, revision_id: UUID, title: str, key: str) -> dict:
        validate_title(title)
        # A durable receipt is not an authorization grant after target membership revocation.
        with self.transactions() as session:
            self._authorize(session, project_id, actor_id, revision_id)

        def operation(session):
            revision = self._authorize(session, project_id, actor_id, revision_id)
            conversation = self.conversations.create_root(session, project_id, title, actor_id)
            conversation_id = UUID(conversation["id"])
            self.inputs.add(session, conversation_id, revision, actor_id)
            now = utc_now()
            self.events.after_commit(session, ProjectEvent(
                project_id, EventName.CONVERSATION_CREATED, now,
                {"project_id": project_id, "conversation": conversation},
            ))
            self.events.after_commit(session, ProjectEvent(
                project_id, EventName.CONVERSATION_INPUTS_UPDATED, now,
                {"conversation_id": conversation_id},
            ))
            return conversation

        return self.idempotency.execute_once(
            str(actor_id), f"sharing.from-result:{project_id}", key,
            {"result_revision_id": str(revision_id), "title": title}, operation,
        )

    def _input_projects(self, session, conversation_id: UUID, actor_id: UUID) -> set[UUID]:
        projects = set(self.memberships.project_ids(session, actor_id))
        if self.conversations.project_id(session, conversation_id) not in projects:
            raise missing()
        return projects

    def _input_metadata(self, session, item: PinnedConclusion, projects: set[UUID]) -> dict:
        revision = self.conclusions.get(session, item.result_revision_id)
        # Latest source metadata is visible only to members of the source project.
        latest = revision.latest_version if revision and revision.project_id in projects else item.version
        return {
            "id": item.id, "conversation_id": item.conversation_id, "result_id": item.result_id,
            "result_revision_id": item.result_revision_id, "version": item.version, "title": item.title,
            "latest_version": latest, "origin": item.origin, "created_by": item.created_by,
            "created_at": item.created_at,
        }

    def list_inputs(self, conversation_id: UUID, actor_id: UUID) -> dict:
        with self.transactions() as session:
            projects = self._input_projects(session, conversation_id, actor_id)
            return {"items": [self._input_metadata(session, item, projects)
                              for item in self.inputs.list(session, conversation_id)]}

    def input_detail(self, conversation_id: UUID, input_id: UUID, actor_id: UUID) -> dict:
        with self.transactions() as session:
            projects = self._input_projects(session, conversation_id, actor_id)
            item = next((item for item in self.inputs.list(session, conversation_id) if item.id == input_id), None)
            if item is None:
                raise missing()
            # Read the stored input's contents, never the original result or its newest version.
            return {**self._input_metadata(session, item, projects),
                    "conclusion": item.conclusion, "source": item.source}
