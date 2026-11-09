"""Pure conversation rules: ancestry, exact content, mentions, and safe author projections."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest

from ramus_api.modules.conversations.domain.models import AuthorKind
from ramus_api.modules.conversations.domain.views import (
    ConversationRecord,
    MessageRecord,
    ancestor_paths,
    conversation_json,
    mentions_ai,
    message_json,
    validate_text,
)

PROJECT, ROOT, CHILD, LEAF, ACCOUNT, RUN = (UUID(int=n) for n in range(1, 7))
AT = datetime(2026, 11, 9, tzinfo=UTC)


def conversation(identifier: UUID, title: str, parent_id: UUID | None = None) -> ConversationRecord:
    return ConversationRecord(identifier, PROJECT, parent_id, None, title, ACCOUNT, AT)


def test_ancestry_is_root_first_and_excludes_the_conversation_itself() -> None:
    records = (
        conversation(LEAF, "같은 제목", CHILD),
        conversation(ROOT, "과제"),
        conversation(CHILD, "조사", ROOT),
        conversation(UUID(int=99), "같은 제목", ROOT),
    )
    paths = ancestor_paths(records)
    assert paths[ROOT] == ()
    assert paths[CHILD] == ("과제",)
    assert paths[LEAF] == ("과제", "조사")
    assert paths[UUID(int=99)] == ("과제",)
    assert conversation_json(records[0], paths[LEAF])["path"] == ["과제", "조사"]


def test_an_empty_project_has_no_paths() -> None:
    assert ancestor_paths(()) == {}


@pytest.mark.parametrize(
    "records",
    [
        (conversation(ROOT, "자기 참조", ROOT),),
        (conversation(ROOT, "A", CHILD), conversation(CHILD, "B", ROOT)),
        (conversation(CHILD, "누락 부모", ROOT),),
        (conversation(ROOT, "부모"), replace(conversation(CHILD, "다른 프로젝트", ROOT), project_id=RUN)),
    ],
)
def test_invalid_ancestry_never_silently_emits_a_misleading_path(records) -> None:
    with pytest.raises(ValueError):
        ancestor_paths(records)


@pytest.mark.parametrize("body", ["@AI 조사해 줘", "다음 항목을 @ai 에 요청", "앞말@aI뒷말"])
def test_ai_mentions_ignore_case_and_follow_the_contract_substring_rule(body: str) -> None:
    assert mentions_ai(body)


@pytest.mark.parametrize("body", ["AI 조사해 줘", "지훈님 조사해 주세요", "메일은 ai@example.test", ""])
def test_ordinary_discussion_does_not_request_a_run(body: str) -> None:
    assert not mentions_ai(body)


def test_validation_preserves_original_body_and_accepts_the_exact_limit() -> None:
    text = "  첫 줄\n다음 줄\t"
    assert validate_text(text, len(text)) == text
    assert validate_text("가" * 20_000, 20_000) == "가" * 20_000


@pytest.mark.parametrize("text", ["", " \t\r\n", "\u3000", "가" * 101])
def test_validation_rejects_blank_or_overlong_title(text: str) -> None:
    with pytest.raises(ValueError):
        validate_text(text, 100)


@pytest.mark.parametrize("text", ["private\x00text", "\ud800", "text\udfff"])
def test_validation_rejects_text_postgresql_cannot_store_without_echoing_it(text: str) -> None:
    with pytest.raises(ValueError) as caught:
        validate_text(text, 20_000)
    assert text not in str(caught.value)


def message(kind: AuthorKind = AuthorKind.HUMAN) -> MessageRecord:
    return MessageRecord(ROOT, CHILD, 42, kind, ACCOUNT, None, "본문", None, None, AT)


def test_human_author_is_looked_up_from_the_server_account_map() -> None:
    response = message_json(message(), {ACCOUNT: "참여자"})
    assert response["author"] == {"kind": "human", "account_id": str(ACCOUNT), "display_name": "참여자"}
    assert response["is_example"] is False
    assert response["requested_by"] is response["run_id"] is None


def test_example_author_label_is_kept_without_a_real_account() -> None:
    example = replace(message(), author_account_id=None, example_author_label="예시 작성자")
    response = message_json(example, {})
    assert response["author"] == {"kind": "human", "account_id": None, "display_name": "예시 작성자"}
    assert response["is_example"] is True


@pytest.mark.parametrize("kind,label", [(AuthorKind.AI, "AI"), (AuthorKind.SYSTEM, "시스템")])
def test_automated_message_keeps_requester_separate_from_its_author(kind: AuthorKind, label: str) -> None:
    automated = replace(message(kind), author_account_id=None, requested_by=ACCOUNT, run_id=RUN)
    response = message_json(automated, {})
    assert response["author"] == {"kind": kind.value, "account_id": None, "display_name": label}
    assert response["requested_by"] == str(ACCOUNT)
    assert response["run_id"] == str(RUN)
