"""Pure resource rules (B1): content per kind, file type (D9), selection of pinned revisions."""

from uuid import uuid4

import pytest

from ramus_api.modules.resources.domain.models import ResourceKind
from ramus_api.modules.resources.domain.rules import (
    MAX_NAME_LENGTH,
    MAX_TEXT_LENGTH,
    ResourceRuleError,
    RevisionContent,
    RevisionRef,
    check_applied_selection,
    content_hash,
    normalize_content,
)


def skill(**overrides):
    values = {
        "name": " 벤치마킹 ",
        "description": " 조사 기준 ",
        "instructions": " 항목별로 비교한다 ",
        "content": None,
        "file_name": None,
    }
    return normalize_content(ResourceKind.SKILL, **{**values, **overrides})


def rule_error(call) -> ResourceRuleError:
    with pytest.raises(ResourceRuleError) as caught:
        call()
    return caught.value


class TestNormalizeContent:
    def test_skill_keeps_instructions_and_trims(self) -> None:
        assert skill() == RevisionContent("벤치마킹", "조사 기준", "항목별로 비교한다", None, None)

    def test_description_may_be_empty(self) -> None:
        assert skill(description="  ").description == ""

    @pytest.mark.parametrize("field", ["name", "instructions"])
    @pytest.mark.parametrize("value", ["", "   ", None])
    def test_blank_name_or_instructions_is_rejected(self, field: str, value) -> None:
        error = rule_error(lambda: skill(**{field: value}))
        assert error.code == "INVALID_INPUT"
        assert error.details == {"field": field, "reason": "required"}

    def test_too_long_values_are_rejected(self) -> None:
        assert rule_error(lambda: skill(name="가" * (MAX_NAME_LENGTH + 1))).details["reason"] == "too_long"
        assert (
            rule_error(lambda: skill(instructions="a" * (MAX_TEXT_LENGTH + 1))).details["field"]
            == "instructions"
        )

    def test_skill_rejects_content_and_file_name(self) -> None:
        assert rule_error(lambda: skill(content="x")).details == {"field": "content", "reason": "not_allowed"}
        assert rule_error(lambda: skill(file_name="a.md")).details["field"] == "file_name"

    def test_text_needs_content_only(self) -> None:
        text = normalize_content(
            ResourceKind.TEXT,
            name="정책",
            description="",
            instructions=None,
            content=" 본문 ",
            file_name=None,
        )
        assert text == RevisionContent("정책", "", None, "본문", None)
        error = rule_error(
            lambda: normalize_content(
                ResourceKind.TEXT,
                name="정책",
                description="",
                instructions="x",
                content="본문",
                file_name=None,
            )
        )
        assert error.details["field"] == "instructions"

    @pytest.mark.parametrize("file_name", ["SKILL.md", "notes.TXT", "a.b.md"])
    def test_file_accepts_md_and_txt(self, file_name: str) -> None:
        result = normalize_content(
            ResourceKind.FILE,
            name="자료",
            description="",
            instructions=None,
            content="# 제목",
            file_name=file_name,
        )
        assert result.file_name == file_name

    @pytest.mark.parametrize("file_name", ["slides.pdf", "md", "notes.md.exe"])
    def test_file_rejects_other_types(self, file_name: str) -> None:
        error = rule_error(
            lambda: normalize_content(
                ResourceKind.FILE,
                name="자료",
                description="",
                instructions=None,
                content="x",
                file_name=file_name,
            )
        )
        assert error.code == "FILE_TYPE_UNSUPPORTED"

    def test_file_rejects_binary_content(self) -> None:
        error = rule_error(
            lambda: normalize_content(
                ResourceKind.FILE,
                name="자료",
                description="",
                instructions=None,
                content="a\x00b",
                file_name="a.md",
            )
        )
        assert error.code == "FILE_TYPE_UNSUPPORTED"

    def test_file_requires_a_name(self) -> None:
        error = rule_error(
            lambda: normalize_content(
                ResourceKind.FILE, name="자료", description="", instructions=None, content="x", file_name=None
            )
        )
        assert error.details == {"field": "file_name", "reason": "required"}


class TestContentHash:
    def test_same_content_same_hash(self) -> None:
        assert content_hash(skill()) == content_hash(skill(name="벤치마킹"))

    def test_any_field_change_changes_hash(self) -> None:
        base = content_hash(skill())
        assert content_hash(skill(description="다른 설명")) != base
        assert content_hash(skill(instructions="다른 지침")) != base

    def test_field_boundaries_are_not_ambiguous(self) -> None:
        a = RevisionContent("ab", "c", "x", None, None)
        b = RevisionContent("a", "bc", "x", None, None)
        assert content_hash(a) != content_hash(b)


class TestAppliedSelection:
    project = uuid4()

    def ref(self, resource=None, project=None) -> RevisionRef:
        return RevisionRef(uuid4(), resource or uuid4(), project or self.project)

    def test_keeps_request_order_and_drops_exact_duplicates(self) -> None:
        a, b = self.ref(), self.ref()
        result = check_applied_selection([b.revision_id, a.revision_id, b.revision_id], [a, b], self.project)
        assert result == (b, a)

    def test_empty_selection_clears(self) -> None:
        assert check_applied_selection([], [], self.project) == ()

    def test_unknown_and_other_project_ids_are_reported_together(self) -> None:
        other = self.ref(project=uuid4())
        missing = uuid4()
        error = rule_error(
            lambda: check_applied_selection([other.revision_id, missing], [other], self.project)
        )
        assert error.code == "INVALID_INPUT"
        assert error.details["ids"] == [str(other.revision_id), str(missing)]

    def test_two_versions_of_one_resource_are_rejected(self) -> None:
        resource = uuid4()
        v1, v2 = self.ref(resource), self.ref(resource)
        error = rule_error(
            lambda: check_applied_selection([v1.revision_id, v2.revision_id], [v1, v2], self.project)
        )
        assert error.details["reason"] == "one_revision_per_resource"
