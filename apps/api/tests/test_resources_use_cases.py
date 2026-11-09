"""B1 use cases against the real schema: register v1, search, and pin exact versions (F-08·F-09)."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ramus_api.modules.access.infrastructure.models import AccountRow, MembershipRow
from ramus_api.modules.conversations.infrastructure.models import ConversationRow
from ramus_api.modules.projects.infrastructure.models import ProjectRow
from ramus_api.modules.realtime.domain.events import EventName
from ramus_api.modules.resources.application.use_cases import ResourceDraft, ResourceUseCases
from ramus_api.modules.resources.domain.models import ResourceKind
from ramus_api.modules.resources.domain.rules import ResourceRuleError
from ramus_api.modules.resources.infrastructure.models import (
    ConversationResourceRow,
    ResourceRevisionRow,
    ResourceRow,
)
from ramus_api.modules.resources.infrastructure.repository import SqlResourceRepository
from ramus_api.shared.infrastructure.database import Database

pytestmark = pytest.mark.integration

NOW = datetime(2026, 11, 9, 4, 0, tzinfo=UTC)


class SqlMembership:
    """Test stand-in for track A's membership port: reads membership directly."""

    def is_member(self, session: Session, account_id: UUID, project_id: UUID) -> bool:
        return (
            session.scalar(
                select(MembershipRow.account_id).where(
                    MembershipRow.account_id == account_id, MembershipRow.project_id == project_id
                )
            )
            is not None
        )


class SqlConversations:
    """Test stand-in for track A's conversation lookup port."""

    def project_of(self, session: Session, conversation_id: UUID) -> UUID | None:
        return session.scalar(select(ConversationRow.project_id).where(ConversationRow.id == conversation_id))


@dataclass
class World:
    database: Database
    use_cases: ResourceUseCases[Session]
    member: UUID
    outsider: UUID
    project: UUID
    other_project: UUID
    conversation: UUID
    other_conversation: UUID
    ids: list[UUID] = field(default_factory=list)

    def tx(self):
        return self.database.transaction()


def _seed(session: Session) -> dict[str, UUID]:
    ids = {
        name: uuid4()
        for name in ("member", "outsider", "project", "other_project", "conversation", "other_conversation")
    }
    session.execute(
        insert(AccountRow),
        [
            {"id": ids["member"], "email": f"{ids['member']}@example.com", "display_name": "민서"},
            {"id": ids["outsider"], "email": f"{ids['outsider']}@example.com", "display_name": "외부"},
        ],
    )
    session.execute(
        insert(ProjectRow),
        [
            {"id": ids["project"], "name": "신규 서비스 기획", "is_shared_sample": False},
            {"id": ids["other_project"], "name": "다른 프로젝트", "is_shared_sample": False},
        ],
    )
    session.execute(
        insert(MembershipRow),
        [
            {"account_id": ids["member"], "project_id": ids["project"], "role": "editor"},
            {"account_id": ids["member"], "project_id": ids["other_project"], "role": "editor"},
            {"account_id": ids["outsider"], "project_id": ids["other_project"], "role": "editor"},
        ],
    )
    session.execute(
        insert(ConversationRow),
        [
            {
                "id": ids["conversation"],
                "project_id": ids["project"],
                "title": "서비스 방향",
                "origin": "top",
                "created_by": ids["member"],
            },
            {
                "id": ids["other_conversation"],
                "project_id": ids["other_project"],
                "title": "다른 대화",
                "origin": "top",
                "created_by": ids["member"],
            },
        ],
    )
    return ids


@pytest.fixture
def world(database: Database) -> Iterator[World]:
    with database.transaction() as session:
        ids = _seed(session)
    use_cases = ResourceUseCases(
        repository=SqlResourceRepository(),
        membership=SqlMembership(),
        conversations=SqlConversations(),
        new_id=uuid4,
        now=lambda: NOW,
    )
    yield World(database, use_cases, **ids)


def skill(
    name: str = "벤치마킹 스킬",
    description: str = "쇼핑몰 조사 기준",
    instructions: str = "항목별로 비교한다",
) -> ResourceDraft:
    return ResourceDraft(ResourceKind.SKILL, name, description, instructions, None, None)


def create(world: World, draft: ResourceDraft | None = None, project: UUID | None = None):
    with world.tx() as session:
        return world.use_cases.create(session, world.member, project or world.project, draft or skill())


def add_revision(world: World, resource_id: UUID, name: str) -> UUID:
    """Simulates B2 saving v2 so pinning can be checked against a newer latest version."""
    with world.tx() as session:
        latest = session.scalar(select(ResourceRow.latest_revision_id).where(ResourceRow.id == resource_id))
        number = (
            session.scalar(select(ResourceRevisionRow.number).where(ResourceRevisionRow.id == latest)) + 1
        )
        revision_id = uuid4()
        session.execute(
            insert(ResourceRevisionRow).values(
                id=revision_id,
                resource_id=resource_id,
                number=number,
                name=name,
                description="",
                instructions="새 지침",
                content=None,
                file_name=None,
                content_hash="x" * 64,
                base_revision_id=latest,
                created_by=world.member,
            )
        )
        session.execute(
            update(ResourceRow).where(ResourceRow.id == resource_id).values(latest_revision_id=revision_id)
        )
    return revision_id


def rule_code(call) -> str:
    with pytest.raises(ResourceRuleError) as caught:
        call()
    return caught.value.code


class TestCreate:
    def test_creates_v1_with_author_and_event(self, world: World) -> None:
        outcome = create(world)
        history = outcome.value
        latest = history.resource.latest
        assert history.resource.kind is ResourceKind.SKILL
        assert (latest.number, latest.content.name, latest.content.instructions) == (
            1,
            "벤치마킹 스킬",
            "항목별로 비교한다",
        )
        assert latest.created_by == world.member
        assert [entry.number for entry in history.revisions] == [1]
        (event,) = outcome.events
        assert event.name is EventName.RESOURCE_UPDATED
        assert event.project_id == world.project
        assert dict(event.data) == {
            "project_id": str(world.project),
            "resource_id": str(history.resource.id),
            "latest_revision_id": str(latest.id),
            "latest_number": 1,
        }

    def test_stores_file_content_and_name_in_the_revision(self, world: World) -> None:
        draft = ResourceDraft(ResourceKind.FILE, "SKILL.md", "", None, "# 지침\n본문", "SKILL.md")
        latest = create(world, draft).value.resource.latest
        assert (latest.content.content, latest.content.file_name) == ("# 지침\n본문", "SKILL.md")

    def test_non_member_cannot_create_and_nothing_is_written(self, world: World) -> None:
        with world.tx() as session:
            before = session.scalar(select(ResourceRow.id).where(ResourceRow.project_id == world.project))
            assert (
                rule_code(lambda: world.use_cases.create(session, world.outsider, world.project, skill()))
                == "NOT_FOUND"
            )
        assert before is None
        with world.tx() as session:
            assert (
                session.scalar(select(ResourceRow.id).where(ResourceRow.project_id == world.project)) is None
            )

    def test_invalid_content_writes_nothing(self, world: World) -> None:
        with world.tx() as session:
            assert (
                rule_code(
                    lambda: world.use_cases.create(
                        session, world.member, world.project, skill(instructions=" ")
                    )
                )
                == "INVALID_INPUT"
            )
            assert (
                session.scalar(select(ResourceRow.id).where(ResourceRow.project_id == world.project)) is None
            )


class TestSearch:
    def test_matches_name_or_description_case_insensitively_sorted_by_name(self, world: World) -> None:
        create(world, skill(name="Benchmark", description="경쟁사 조사"))
        create(world, skill(name="고객 인터뷰", description="benchmark 결과 정리"))
        create(world, skill(name="무관", description="없음"))
        with world.tx() as session:
            hits = world.use_cases.search(session, world.member, world.project, " BENCH ", None)
        assert [hit.resource.latest.content.name for hit in hits] == ["Benchmark", "고객 인터뷰"]
        assert all(hit.applied is None for hit in hits)

    def test_empty_query_lists_everything_in_the_project_only(self, world: World) -> None:
        create(world, skill(name="이 프로젝트"))
        create(world, skill(name="다른 프로젝트 자료"), project=world.other_project)
        with world.tx() as session:
            hits = world.use_cases.search(session, world.member, world.project, "", None)
        assert [hit.resource.latest.content.name for hit in hits] == ["이 프로젝트"]

    def test_like_wildcards_are_literal(self, world: World) -> None:
        create(world, skill(name="100% 기준"))
        create(world, skill(name="1000 기준"))
        with world.tx() as session:
            hits = world.use_cases.search(session, world.member, world.project, "100%", None)
        assert [hit.resource.latest.content.name for hit in hits] == ["100% 기준"]

    def test_shows_applied_version_next_to_latest(self, world: World) -> None:
        resource = create(world).value.resource
        with world.tx() as session:
            world.use_cases.replace_applied(session, world.member, world.conversation, [resource.latest.id])
        v2 = add_revision(world, resource.id, "벤치마킹 스킬")
        with world.tx() as session:
            (hit,) = world.use_cases.search(session, world.member, world.project, "", world.conversation)
        assert (hit.resource.latest.id, hit.resource.latest.number) == (v2, 2)
        assert (hit.applied.revision_id, hit.applied.number) == (resource.latest.id, 1)

    def test_non_member_and_foreign_conversation_get_not_found(self, world: World) -> None:
        with world.tx() as session:
            assert (
                rule_code(lambda: world.use_cases.search(session, world.outsider, world.project, "", None))
                == "NOT_FOUND"
            )
            assert (
                rule_code(
                    lambda: world.use_cases.search(
                        session, world.member, world.project, "", world.other_conversation
                    )
                )
                == "NOT_FOUND"
            )


class TestApplied:
    def test_replace_pins_exact_versions_and_emits_event(self, world: World) -> None:
        a = create(world, skill(name="가 스킬")).value.resource
        b = create(world, skill(name="나 스킬")).value.resource
        with world.tx() as session:
            outcome = world.use_cases.replace_applied(
                session, world.member, world.conversation, [b.latest.id, a.latest.id]
            )
        assert [(i.name, i.number, i.kind) for i in outcome.value] == [
            ("가 스킬", 1, ResourceKind.SKILL),
            ("나 스킬", 1, ResourceKind.SKILL),
        ]
        (event,) = outcome.events
        assert (event.name, dict(event.data)) == (
            EventName.CONVERSATION_RESOURCES_UPDATED,
            {"conversation_id": str(world.conversation)},
        )

    def test_saving_a_newer_version_does_not_move_the_pin(self, world: World) -> None:
        resource = create(world).value.resource
        with world.tx() as session:
            world.use_cases.replace_applied(session, world.member, world.conversation, [resource.latest.id])
        add_revision(world, resource.id, "벤치마킹 스킬 v2")
        with world.tx() as session:
            (applied,) = world.use_cases.list_applied(session, world.member, world.conversation)
        assert (applied.revision_id, applied.number, applied.name) == (resource.latest.id, 1, "벤치마킹 스킬")

    def test_explicitly_applying_v2_switches_and_empty_list_clears(self, world: World) -> None:
        resource = create(world).value.resource
        with world.tx() as session:
            world.use_cases.replace_applied(session, world.member, world.conversation, [resource.latest.id])
        v2 = add_revision(world, resource.id, "벤치마킹 스킬")
        with world.tx() as session:
            (applied,) = world.use_cases.replace_applied(
                session, world.member, world.conversation, [v2]
            ).value
        assert (applied.revision_id, applied.number) == (v2, 2)
        with world.tx() as session:
            assert world.use_cases.replace_applied(session, world.member, world.conversation, []).value == ()
            assert world.use_cases.list_applied(session, world.member, world.conversation) == ()

    def test_same_selection_again_is_a_no_op_without_event(self, world: World) -> None:
        resource = create(world).value.resource
        with world.tx() as session:
            world.use_cases.replace_applied(session, world.member, world.conversation, [resource.latest.id])
        with world.tx() as session:
            outcome = world.use_cases.replace_applied(
                session, world.member, world.conversation, [resource.latest.id]
            )
        assert outcome.events == ()
        assert len(outcome.value) == 1

    def test_rejects_other_project_revision_and_keeps_previous_pins(self, world: World) -> None:
        mine = create(world).value.resource
        theirs = create(world, project=world.other_project).value.resource
        with world.tx() as session:
            world.use_cases.replace_applied(session, world.member, world.conversation, [mine.latest.id])
        with world.tx() as session:
            assert (
                rule_code(
                    lambda: world.use_cases.replace_applied(
                        session, world.member, world.conversation, [theirs.latest.id]
                    )
                )
                == "INVALID_INPUT"
            )
        with world.tx() as session:
            (applied,) = world.use_cases.list_applied(session, world.member, world.conversation)
        assert applied.revision_id == mine.latest.id

    def test_rejects_two_versions_of_one_resource(self, world: World) -> None:
        resource = create(world).value.resource
        v2 = add_revision(world, resource.id, "v2")
        with world.tx() as session:
            assert (
                rule_code(
                    lambda: world.use_cases.replace_applied(
                        session, world.member, world.conversation, [resource.latest.id, v2]
                    )
                )
                == "INVALID_INPUT"
            )

    def test_non_member_and_unknown_conversation_get_not_found(self, world: World) -> None:
        with world.tx() as session:
            assert (
                rule_code(lambda: world.use_cases.list_applied(session, world.outsider, world.conversation))
                == "NOT_FOUND"
            )
            assert (
                rule_code(lambda: world.use_cases.replace_applied(session, world.member, uuid4(), []))
                == "NOT_FOUND"
            )


def test_database_rejects_a_pin_whose_revision_belongs_to_another_resource(world: World) -> None:
    a = create(world, skill(name="가")).value.resource
    b = create(world, skill(name="나")).value.resource
    with pytest.raises(IntegrityError), world.tx() as session:
        session.execute(
            insert(ConversationResourceRow).values(
                conversation_id=world.conversation,
                resource_id=a.id,
                revision_id=b.latest.id,
                applied_by=world.member,
            )
        )
